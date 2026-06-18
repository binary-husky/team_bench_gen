"""
CIFAR-10 training: compare three optimizers (SGD-Momentum, AdamW, Muon) on the
same SmallCNN. Records per-epoch metrics to JSONL.
"""
import argparse
import json
import os
import sys
import time

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import SmallCNN, split_params_for_muon, split_params_for_policy, PARAM_POLICIES  # noqa
from muon import Muon  # noqa
from parquet_ds import ParquetCifar10  # noqa


CIFAR_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR_STD = (0.2470, 0.2435, 0.2616)


def get_loaders(data_dir, batch_size=128, num_workers=4):
    train_tf = T.Compose([
        T.RandomCrop(32, padding=4),
        T.RandomHorizontalFlip(),
        T.ToTensor(),
        T.Normalize(CIFAR_MEAN, CIFAR_STD),
    ])
    test_tf = T.Compose([
        T.ToTensor(),
        T.Normalize(CIFAR_MEAN, CIFAR_STD),
    ])
    train_set = ParquetCifar10(data_dir, train=True, transform=train_tf)
    test_set = ParquetCifar10(data_dir, train=False, transform=test_tf)
    train_loader = torch.utils.data.DataLoader(
        train_set, batch_size=batch_size, shuffle=True, num_workers=num_workers,
        pin_memory=True, drop_last=False,
    )
    test_loader = torch.utils.data.DataLoader(
        test_set, batch_size=512, shuffle=False, num_workers=num_workers,
        pin_memory=True,
    )
    return train_loader, test_loader


def make_optimizer(name, model, lr, weight_decay, ns_abc=None, param_policy="hidden_2d",
                    update_scaling="paper", spectral_max_norm=1.0,
                    muon_momentum=0.95, nesterov=True, aux_lr_ratio=0.05):
    if param_policy == "hidden_2d":
        muon_params, adamw_params = split_params_for_muon(model)
    else:
        muon_params, adamw_params = split_params_for_policy(model, param_policy)
    if name == "sgd":
        return torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9,
                               weight_decay=weight_decay, nesterov=True)
    elif name == "adamw":
        return torch.optim.AdamW(model.parameters(), lr=lr,
                                 betas=(0.9, 0.999), weight_decay=weight_decay)
    elif name == "muon":
        # Muon for hidden weights, AdamW for biases/head — per paper.
        abc = (3.4445, -4.7750, 2.0315) if ns_abc is None else ns_abc
        return Muon(muon_params, lr=lr, momentum=muon_momentum, nesterov=nesterov,
                    weight_decay=weight_decay, ns_steps=5, ns_abc=abc,
                    update_scaling=update_scaling,
                    spectral_max_norm=spectral_max_norm), \
               torch.optim.AdamW(adamw_params, lr=lr * aux_lr_ratio,
                                 betas=(0.9, 0.95), weight_decay=weight_decay)
    else:
        raise ValueError(f"Unknown optimizer: {name}")


def make_scheduler(opt, milestones, gamma=0.1):
    return torch.optim.lr_scheduler.MultiStepLR(opt, milestones=milestones, gamma=gamma)


def evaluate(model, loader, device, label_smoothing=0.0):
    model.eval()
    correct, total, loss_sum = 0, 0, 0.0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            logits = model(x)
            loss = F.cross_entropy(logits, y, reduction="sum", label_smoothing=label_smoothing)
            loss_sum += loss.item()
            correct += (logits.argmax(1) == y).sum().item()
            total += y.size(0)
    return loss_sum / total, correct / total


def train_one_epoch(model, loader, opts, device, scaler, use_amp, label_smoothing=0.0):
    model.train()
    loss_sum, correct, total = 0.0, 0, 0
    for x, y in loader:
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        for opt in opts:
            opt.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", enabled=use_amp, dtype=torch.bfloat16):
            logits = model(x)
            loss = F.cross_entropy(logits, y, label_smoothing=label_smoothing)
        if use_amp and scaler is not None:
            scaler.scale(loss).backward()
            for opt in opts:
                scaler.step(opt)
            scaler.update()
        else:
            loss.backward()
            for opt in opts:
                opt.step()
        loss_sum += loss.item() * y.size(0)
        correct += (logits.argmax(1) == y).sum().item()
        total += y.size(0)
    return loss_sum / total, correct / total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--optimizer", choices=["sgd", "adamw", "muon"], required=True)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=None,
                    help="Override default learning rate for the optimizer.")
    ap.add_argument("--weight-decay", type=float, default=5e-4)
    ap.add_argument("--data-dir", default="/tmp/cifar10_smoke",
                    help="Directory holding cifar-train.parquet and cifar-test.parquet")
    ap.add_argument("--out", default="results")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--no-amp", action="store_true")
    ap.add_argument("--milestones", nargs="+", type=int, default=[20, 25])
    ap.add_argument("--gamma", type=float, default=0.1)
    ap.add_argument("--ns-abc", type=str, default=None,
                    help='Override Newton-Schulz coefficients as "a,b,c" (muon only)')
    ap.add_argument("--param-policy", type=str, default="hidden_2d",
                    choices=list(PARAM_POLICIES),
                    help="Parameter-grouping policy (muon only)")
    ap.add_argument("--dropout", type=float, default=0.2,
                    help="Dropout rate in SmallCNN head (default 0.2)")
    ap.add_argument("--label-smoothing", type=float, default=0.0,
                    help="Label smoothing for cross-entropy (default 0.0)")
    ap.add_argument("--width-factor", type=float, default=1.0,
                    help="Scale SmallCNN hidden channels by this factor (default 1.0)")
    ap.add_argument("--tag", type=str, default="",
                    help="Optional tag suffix for output filename (e.g. 'wd1e-3')")
    ap.add_argument("--update-scaling", type=str, default="paper",
                    choices=["paper", "none", "sqrt_rows_cols", "rms_match", "spectral_clip"],
                    help="Muon update scaling mode (default 'paper')")
    ap.add_argument("--spectral-max-norm", type=float, default=1.0,
                    help="Max spectral norm for 'spectral_clip' mode (default 1.0)")
    ap.add_argument("--muon-momentum", type=float, default=0.95,
                    help="Momentum for Muon (default 0.95)")
    ap.add_argument("--no-nesterov", action="store_true",
                    help="Disable Nesterov momentum for Muon (default: enabled)")
    ap.add_argument("--aux-lr-ratio", type=float, default=0.05,
                    help="Aux AdamW lr as a ratio of Muon lr (default 0.05)")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = True

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[setup] device={device} optim={args.optimizer} epochs={args.epochs} "
          f"bs={args.batch_size} amp={not args.no_amp}")

    os.makedirs(args.out, exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    out_file = os.path.join(args.out, f"{args.optimizer}_{args.param_policy}{suffix}.jsonl")

    train_loader, test_loader = get_loaders(args.data_dir, args.batch_size, args.num_workers)
    model = SmallCNN(dropout=args.dropout, width_factor=args.width_factor).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[setup] model params = {n_params/1e6:.2f}M  dropout={args.dropout} "
          f"label_smoothing={args.label_smoothing} width_factor={args.width_factor}")

    # Default LRs chosen to be reasonable for each optimizer on this model
    default_lr = {"sgd": 0.1, "adamw": 3e-3, "muon": 0.02}[args.optimizer]
    lr = args.lr if args.lr is not None else default_lr
    print(f"[setup] lr={lr} weight_decay={args.weight_decay}")

    opts = make_optimizer(args.optimizer, model, lr, args.weight_decay,
                          ns_abc=tuple(float(x) for x in args.ns_abc.split(",")) if args.ns_abc else None,
                          param_policy=args.param_policy,
                          update_scaling=args.update_scaling,
                          spectral_max_norm=args.spectral_max_norm,
                          muon_momentum=args.muon_momentum,
                          nesterov=not args.no_nesterov,
                          aux_lr_ratio=args.aux_lr_ratio)
    if not isinstance(opts, tuple):
        opts = (opts,)
    schedulers = [make_scheduler(opt, args.milestones, args.gamma) for opt in opts]

    use_amp = not args.no_amp and torch.cuda.is_available()
    scaler = torch.amp.GradScaler("cuda", enabled=False)  # bf16 doesn't need GradScaler

    log = []
    best_acc = 0.0
    t0 = time.time()
    with open(out_file, "w") as f:
        for epoch in range(args.epochs):
            tr_loss, tr_acc = train_one_epoch(model, train_loader, opts, device, scaler, use_amp,
                                              label_smoothing=args.label_smoothing)
            te_loss, te_acc = evaluate(model, test_loader, device,
                                       label_smoothing=args.label_smoothing)
            for sch in schedulers:
                sch.step()
            elapsed = time.time() - t0
            record = {
                "epoch": epoch + 1,
                "train_loss": tr_loss,
                "train_acc": tr_acc,
                "val_loss": te_loss,
                "val_acc": te_acc,
                "lr": opts[0].param_groups[0]["lr"],
                "elapsed_sec": elapsed,
                "width_factor": args.width_factor,
                "n_params": n_params,
            }
            log.append(record)
            f.write(json.dumps(record) + "\n")
            f.flush()
            best_acc = max(best_acc, te_acc)
            cur_lr = record["lr"]
            print(f"[epoch {epoch+1:02d}/{args.epochs}] "
                  f"tr_loss={tr_loss:.4f} tr_acc={tr_acc:.4f} "
                  f"te_loss={te_loss:.4f} te_acc={te_acc:.4f} "
                  f"best={best_acc:.4f} lr={cur_lr:.5f} t={elapsed:.1f}s")

    print(f"[done] best_val_acc={best_acc:.4f}  total_time={time.time()-t0:.1f}s")
    print(f"[done] log -> {out_file}")


if __name__ == "__main__":
    main()
