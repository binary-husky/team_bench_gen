"""
课题 5 — Muon update spectrum / effective rank 诊断。

训练 Muon / SGD-Momentum / AdamW 各 10 epoch；每 epoch 结束后用固定 batch
做一次诊断，记录 5 个目标层的：
  - gradient         (last batch 的 .grad, reshape 成 2D)
  - momentum buffer  (Muon/SGD: state['momentum_buffer'];
                      AdamW: state['exp_avg'])
  - final update     (optimizer 实际加到 param 上的 Δp/lr, 即"pre-lr" update)
对每层都计算 spectral norm / Frobenius norm / effective rank / top-10
singular values。

输出: results/spectrum/{optim}.jsonl  (每行一个 layer×epoch 的诊断)
"""
import argparse
import copy
import json
import math
import os
import sys
import time

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.transforms as T

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import SmallCNN  # noqa
from muon import Muon  # noqa
from parquet_ds import ParquetCifar10  # noqa


CIFAR_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR_STD = (0.2470, 0.2435, 0.2616)

# 5 个诊断层：name -> (shape_after_2d_reshape)
TARGETS = {
    "stem":            ("stem.weight",            (64, 3 * 3 * 3)),    # (64,27)
    "block1.conv2":    ("block1.conv2.weight",    (64, 64 * 3 * 3)),   # (64,576)
    "block2.conv2":    ("block2.conv2.weight",    (128, 64 * 3 * 3)),  # (128,576)
    "block3.conv2":    ("block3.conv2.weight",    (256, 128 * 3 * 3)), # (256,1152)
    "fc1":             ("fc1.weight",             (128, 256)),          # (128,256)
}

TOPK = 10
EPS = 1e-12


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


def make_optimizer(name, model, lr, weight_decay):
    if name == "sgd":
        return [torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9,
                                weight_decay=weight_decay, nesterov=True)]
    elif name == "adamw":
        return [torch.optim.AdamW(model.parameters(), lr=lr,
                                 betas=(0.9, 0.999), weight_decay=weight_decay)]
    elif name == "muon":
        # Muon for hidden 2D+ (paper default policy)
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


def flatten_2d(t):
    """Reshape any tensor to 2D: (rows, cols) where rows = first dim."""
    if t.ndim == 4:
        return t.view(t.size(0), -1)
    if t.ndim == 2:
        return t
    if t.ndim == 1:
        return t.unsqueeze(0)
    return t.reshape(t.size(0), -1)


def spectrum_stats(t2d, topk=TOPK):
    """Return dict of spectral diagnostics for a 2D tensor."""
    t = t2d.detach().float()
    # Frobenius norm
    fro = t.norm().item()
    # SVD on GPU
    try:
        s = torch.linalg.svdvals(t)
    except Exception:
        # CPU fallback (rare)
        s = torch.linalg.svdvals(t.cpu())
    sigmas = s.cpu().numpy()
    spec = float(sigmas[0]) if len(sigmas) > 0 else 0.0
    # Effective rank: exp(H(p)) where p = sigma/sum(sigma), H = -sum(p log p)
    total = sigmas.sum()
    if total > EPS:
        p = sigmas / total
        p = p[p > EPS]
        H = -(p * np_log(p)).sum()
        eff_rank = float(math.exp(H))
    else:
        eff_rank = 0.0
    # Top-k singular values
    k = min(topk, len(sigmas))
    top = sigmas[:k].tolist()
    return {
        "spec": spec,
        "fro": fro,
        "eff_rank": eff_rank,
        "top_singular": top,
        "n_elem": int(t2d.numel()),
        "shape_2d": list(t2d.shape),
    }


def np_log(x):
    import numpy as np
    return np.log(x)


def collect_diagnostic(model, opts, device, x, y, label_smoothing=0.0):
    """
    Use the provided batch (x, y) to compute diagnostics for the 5 target layers.
    Returns:
      grads    : {layer: 2D grad tensor on cpu}
      moments  : {layer: 2D momentum buffer on cpu}
      updates  : {layer: 2D effective update (Δp / lr) on cpu}

    Procedure:
      1) zero_grad
      2) forward + backward (get grad)
      3) snapshot grad
      4) snapshot pre-step momentum buffer (for muon/sgd/adamw)
      5) call step()
      6) snapshot param Δ = (p_after - p_before) / lr  as "final update"
      7) restore param state via deep-copied snapshot (so training is unchanged)
    """
    grads, moments, updates = {}, {}, {}

    # Snapshot params before step
    name_to_p = dict(model.named_parameters())
    p_snap_before = {n: p.detach().clone() for n, p in name_to_p.items()}
    momentum_snap = {n: None for n in TARGETS.values()}
    for _, (pname, _) in TARGETS.items():
        for opt in opts:
            for group in opt.param_groups:
                for p in group["params"]:
                    if id(p) == id(name_to_p[pname]):
                        st = opt.state[p]
                        if "momentum_buffer" in st:
                            momentum_snap[pname] = st["momentum_buffer"].detach().clone()
                        elif "exp_avg" in st:
                            momentum_snap[pname] = st["exp_avg"].detach().clone()
                        break

    for opt in opts:
        opt.zero_grad(set_to_none=True)
    with torch.amp.autocast("cuda", enabled=True, dtype=torch.bfloat16):
        logits = model(x)
        loss = F.cross_entropy(logits, y, label_smoothing=label_smoothing)
    loss.backward()

    for short, (pname, _) in TARGETS.items():
        p = name_to_p[pname]
        if p.grad is None:
            continue
        grads[short] = flatten_2d(p.grad).detach().cpu()
        if momentum_snap[pname] is not None:
            moments[short] = flatten_2d(momentum_snap[pname]).cpu()

    for opt in opts:
        opt.step()

    for short, (pname, _) in TARGETS.items():
        p = name_to_p[pname]
        lr = opts[0].param_groups[0]["lr"]
        # Δp = p_after - p_before
        delta = (p.detach() - p_snap_before[pname])
        updates[short] = flatten_2d(delta / lr).cpu()

    # restore param to before step (so cumulative training isn't disturbed)
    with torch.no_grad():
        for n, p in name_to_p.items():
            p.copy_(p_snap_before[n])

    return grads, moments, updates


def train_one_epoch(model, loader, opts, device, label_smoothing=0.0):
    model.train()
    loss_sum, correct, total = 0.0, 0, 0
    for x, y in loader:
        x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
        for opt in opts:
            opt.zero_grad(set_to_none=True)
        with torch.amp.autocast("cuda", enabled=True, dtype=torch.bfloat16):
            logits = model(x)
            loss = F.cross_entropy(logits, y, label_smoothing=label_smoothing)
        loss.backward()
        for opt in opts:
            opt.step()
        loss_sum += loss.item() * y.size(0)
        correct += (logits.argmax(1) == y).sum().item()
        total += y.size(0)
    return loss_sum / total, correct / total


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--optimizer", choices=["sgd", "adamw", "muon"], required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--weight-decay", type=float, default=5e-4)
    ap.add_argument("--data-dir", default="/tmp/cifar10_smoke")
    ap.add_argument("--out", default="/home/fuqingxu/cc-workspace/muon/results/spectrum")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--milestones", nargs="+", type=int, default=[7, 9])
    ap.add_argument("--gamma", type=float, default=0.1)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--label-smoothing", type=float, default=0.0)
    ap.add_argument("--diag-batch-idx", type=int, default=0,
                    help="Use the diag-batch-idx-th training batch for diagnostics.")
    ap.add_argument("--log-interval", type=int, default=0,
                    help="Optional: print timing breakdown every K epochs.")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = True

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[setup] device={device} optim={args.optimizer} epochs={args.epochs} bs={args.batch_size}")

    os.makedirs(args.out, exist_ok=True)
    out_file = os.path.join(args.out, f"{args.optimizer}.jsonl")

    train_loader, test_loader = get_loaders(args.data_dir, args.batch_size, args.num_workers)
    model = SmallCNN(dropout=args.dropout).to(device)

    default_lr = {"sgd": 0.1, "adamw": 3e-3, "muon": 0.02}[args.optimizer]
    lr = args.lr if args.lr is not None else default_lr
    print(f"[setup] lr={lr} weight_decay={args.weight_decay}")

    opts = make_optimizer(args.optimizer, model, lr, args.weight_decay)
    schedulers = [torch.optim.lr_scheduler.MultiStepLR(opt, args.milestones, gamma=args.gamma)
                  for opt in opts]

    # Pre-fetch the fixed diagnostic batch from the original train set
    diag_iter = iter(train_loader)
    for _ in range(args.diag_batch_idx + 1):
        diag_batch = next(diag_iter)
    diag_x = diag_batch[0].to(device, non_blocking=True)
    diag_y = diag_batch[1].to(device, non_blocking=True)
    # Make sure diag batch has consistent shape (last partial batch)
    print(f"[setup] diag batch shape x={tuple(diag_x.shape)} y={tuple(diag_y.shape)}")

    diag_records = []
    t0 = time.time()
    for epoch in range(args.epochs):
        ep_t = time.time()
        tr_loss, tr_acc = train_one_epoch(model, train_loader, opts, device,
                                          label_smoothing=args.label_smoothing)
        # Diagnostics: re-run on fixed batch
        diags_t = time.time()
        grads, moments, updates = collect_diagnostic(
            model, opts, device, diag_x, diag_y, args.label_smoothing)
        diags_dt = time.time() - diags_t
        # Eval
        te_loss, te_acc = evaluate(model, test_loader, device,
                                   label_smoothing=args.label_smoothing)
        for sch in schedulers:
            sch.step()

        # Build per-layer diag record
        for short, (pname, expected_2d) in TARGETS.items():
            rec = {"epoch": epoch + 1, "layer": short, "param": pname}
            for kind, store in (("grad", grads), ("moment", moments), ("update", updates)):
                if short not in store:
                    rec[kind] = None
                    continue
                stats = spectrum_stats(store[short])
                stats[f"{kind}_shape_2d"] = list(store[short].shape)
                rec[kind] = stats
            rec["val_acc"] = te_acc
            rec["val_loss"] = te_loss
            rec["train_loss"] = tr_loss
            diag_records.append(rec)

        ep_dt = time.time() - ep_t
        elapsed = time.time() - t0
        print(f"[epoch {epoch+1:02d}/{args.epochs}] tr_loss={tr_loss:.4f} "
              f"te_acc={te_acc:.4f} best=? lr={opts[0].param_groups[0]['lr']:.5f} "
              f"ep_t={ep_dt:.1f}s diag={diags_dt:.2f}s t={elapsed:.1f}s")

    # Write JSONL
    with open(out_file, "w") as f:
        for r in diag_records:
            f.write(json.dumps(r) + "\n")
    print(f"[done] {len(diag_records)} diag records -> {out_file}")
    print(f"[done] total_time={time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()