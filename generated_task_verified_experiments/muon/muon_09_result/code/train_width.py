"""课题 7 训练入口：可调宽度 × 优化器 × 学习率网格。

参数：
  --width 0.5/1.0/1.5/2.0
  --optimizer muon/sgd/adamw
  --lr ...（覆盖优化器默认 lr）
  --epochs 10/30

输出：results/width/{optim}_{width}x_{lr}.jsonl
"""
import argparse
import json
import os
import sys
import time

import torch
import torch.nn.functional as F
import torchvision.transforms as T

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import SmallCNN  # noqa
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
    return (
        torch.utils.data.DataLoader(train_set, batch_size=batch_size, shuffle=True,
                                     num_workers=num_workers, pin_memory=True, drop_last=False),
        torch.utils.data.DataLoader(test_set, batch_size=512, shuffle=False,
                                     num_workers=num_workers, pin_memory=True),
    )


def make_optimizer(name, model, lr, weight_decay):
    if name == "sgd":
        return [torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9,
                                weight_decay=weight_decay, nesterov=True)]
    elif name == "adamw":
        return [torch.optim.AdamW(model.parameters(), lr=lr,
                                 betas=(0.9, 0.999), weight_decay=weight_decay)]
    elif name == "muon":
        muon_params, adamw_params = [], []
        for n, p in model.named_parameters():
            if not p.requires_grad:
                continue
            if (p.ndim >= 2) and ("fc2" not in n):
                muon_params.append(p)
            else:
                adamw_params.append(p)
        muon_opt = Muon(muon_params, lr=lr, momentum=0.95, nesterov=True,
                        weight_decay=weight_decay, ns_steps=5,
                        ns_abc=(3.4445, -4.7750, 2.0315),
                        update_scaling="paper", spectral_max_norm=1.0)
        adamw_opt = torch.optim.AdamW(adamw_params, lr=lr * 0.05,
                                      betas=(0.9, 0.95), weight_decay=weight_decay)
        return [muon_opt, adamw_opt]
    else:
        raise ValueError(f"Unknown optimizer: {name}")


DEFAULT_LRS = {"sgd": 0.1, "adamw": 3e-3, "muon": 0.02}


def evaluate(model, loader, device):
    model.eval()
    correct, total, loss_sum = 0, 0, 0.0
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            logits = model(x)
            loss = F.cross_entropy(logits, y, reduction="sum")
            loss_sum += loss.item()
            correct += (logits.argmax(1) == y).sum().item()
            total += y.size(0)
    return loss_sum / total, correct / total


def train_one_epoch(model, loader, opts, device):
    model.train()
    loss_sum, correct, total = 0.0, 0, 0
    for x, y in loader:
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        for opt in opts:
            opt.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", enabled=True, dtype=torch.bfloat16):
            logits = model(x)
            loss = F.cross_entropy(logits, y)
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
    ap.add_argument("--width", type=float, required=True,
                    help="Width multiplier (0.5, 1.0, 1.5, 2.0)")
    ap.add_argument("--lr", type=float, default=None,
                    help="Override default lr; if None, uses optimizer default")
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--weight-decay", type=float, default=5e-4)
    ap.add_argument("--data-dir", default="/tmp/cifar10_smoke")
    ap.add_argument("--out", default="/home/fuqingxu/cc-workspace/muon/results/width")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--milestones", nargs="+", type=int, default=[7, 9])
    ap.add_argument("--gamma", type=float, default=0.1)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--tag", type=str, default="")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = True

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, test_loader = get_loaders(args.data_dir, args.batch_size, args.num_workers)
    model = SmallCNN(dropout=args.dropout, width_factor=args.width).to(device)
    n_params = sum(p.numel() for p in model.parameters())

    default_lr = DEFAULT_LRS[args.optimizer]
    lr = args.lr if args.lr is not None else default_lr
    lr_tag = f"{lr:.4g}"
    print(f"[setup] optim={args.optimizer} width={args.width} epochs={args.epochs} "
          f"bs={args.batch_size} lr={lr} n_params={n_params/1e6:.2f}M")

    os.makedirs(args.out, exist_ok=True)
    width_tag = f"{args.width:.1f}x"
    suffix = f"_{args.tag}" if args.tag else ""
    out_file = os.path.join(args.out, f"{args.optimizer}_{width_tag}_lr{lr_tag}{suffix}.jsonl")

    opts = make_optimizer(args.optimizer, model, lr, args.weight_decay)
    schedulers = [torch.optim.lr_scheduler.MultiStepLR(opt, args.milestones, gamma=args.gamma)
                  for opt in opts]

    log = []
    t0 = time.time()
    with open(out_file, "w") as f:
        for epoch in range(args.epochs):
            ep_t = time.time()
            tr_loss, tr_acc = train_one_epoch(model, train_loader, opts, device)
            te_loss, te_acc = evaluate(model, test_loader, device)
            for sch in schedulers:
                sch.step()
            elapsed = time.time() - t0
            record = {
                "epoch": epoch + 1,
                "train_loss": tr_loss, "train_acc": tr_acc,
                "val_loss": te_loss, "val_acc": te_acc,
                "lr": opts[0].param_groups[0]["lr"],
                "elapsed_sec": elapsed,
            }
            log.append(record)
            f.write(json.dumps(record) + "\n")
            f.flush()
            gap = te_loss - tr_loss
            print(f"[ep {epoch+1:02d}/{args.epochs}] tr_loss={tr_loss:.4f} tr_acc={tr_acc:.4f} "
                  f"te_loss={te_loss:.4f} te_acc={te_acc:.4f} gap={gap:+.4f} "
                  f"lr={opts[0].param_groups[0]['lr']:.5f} ep_t={time.time()-ep_t:.1f}s "
                  f"t={elapsed:.1f}s")

    print(f"[done] best_va={max(r['val_acc'] for r in log):.4f} -> {out_file}")


if __name__ == "__main__":
    main()