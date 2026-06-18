"""Robustness training script — supports 3 dataset variants and 3 optimizers.

Variant selection (mutually exclusive):
  --small-data N         : train on stratified random N samples (5000, 10000, 25000, 50000)
  --label-noise P        : train on full 50k with symmetric noise P in [0,1]
  --long-tail RATIO      : train on long-tail subset with max/min ratio RATIO (10, 50)

If none specified: full 50k clean training (baseline).
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F
import torchvision.transforms as T
from torch.utils.data import Dataset

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import SmallCNN  # noqa
from muon import Muon  # noqa
from parquet_ds import ParquetCifar10  # noqa
from robust_ds import (  # noqa
    SubsetDataset, SymmetricNoiseDataset, LongTailDataset, CleanTestDataset,
)


CIFAR_MEAN = (0.4914, 0.4822, 0.4465)
CIFAR_STD = (0.2470, 0.2435, 0.2616)


def get_loaders(args):
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

    # Decide train set
    n_variants = sum([args.small_data is not None, args.label_noise is not None,
                      args.long_tail is not None])
    if n_variants > 1:
        raise ValueError("Use only one of --small-data / --label-noise / --long-tail.")

    if args.small_data is not None:
        train_set = SubsetDataset(args.data_dir, args.small_data, seed=args.seed)
        variant = f"smalldata_{args.small_data}"
    elif args.label_noise is not None:
        train_set = SymmetricNoiseDataset(args.data_dir, args.label_noise, seed=args.seed)
        variant = f"noise_{args.label_noise}"
    elif args.long_tail is not None:
        train_set = LongTailDataset(args.data_dir, imb_ratio=args.long_tail,
                                    keep_n_max=args.lt_n_max, seed=args.seed)
        variant = f"longtail_{args.long_tail}"
    else:
        train_set = ParquetCifar10(args.data_dir, train=True, transform=train_tf)
        variant = "baseline"

    # Apply transform
    if args.small_data is not None or args.label_noise is not None or args.long_tail is not None:
        # Wrap to apply transform on top of the variant dataset
        class _T(Dataset):
            def __init__(self, base, tf):
                self.base = base
                self.tf = tf
            def __len__(self):
                return len(self.base)
            def __getitem__(self, i):
                img, lbl = self.base[i]
                return self.tf(img), lbl
        train_set = _T(train_set, train_tf)

    test_set = CleanTestDataset(args.data_dir)
    class _TestT(Dataset):
        def __init__(self, base, tf):
            self.base = base; self.tf = tf
        def __len__(self): return len(self.base)
        def __getitem__(self, i):
            img, lbl = self.base[i]
            return self.tf(img), lbl
    test_set = _TestT(test_set, test_tf)

    train_loader = torch.utils.data.DataLoader(
        train_set, batch_size=args.batch_size, shuffle=True,
        num_workers=args.num_workers, pin_memory=True, drop_last=False)
    test_loader = torch.utils.data.DataLoader(
        test_set, batch_size=512, shuffle=False,
        num_workers=args.num_workers, pin_memory=True)
    return train_loader, test_loader, variant, len(train_set)


def make_optimizer(name, model, lr, weight_decay, ns_abc=None,
                    muon_momentum=0.95, nesterov=True, aux_lr_ratio=0.05):
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
        abc = (3.4445, -4.7750, 2.0315) if ns_abc is None else ns_abc
        muon_opt = Muon(muon_params, lr=lr, momentum=muon_momentum,
                        nesterov=nesterov, weight_decay=weight_decay,
                        ns_steps=5, ns_abc=abc,
                        update_scaling="paper", spectral_max_norm=1.0)
        adamw_opt = torch.optim.AdamW(adamw_params, lr=lr * aux_lr_ratio,
                                      betas=(0.9, 0.95), weight_decay=weight_decay)
        return [muon_opt, adamw_opt]
    else:
        raise ValueError(f"Unknown optimizer: {name}")


def per_class_accuracy(model, loader, device, num_classes=10):
    model.eval()
    correct = np.zeros(num_classes, dtype=np.int64)
    total = np.zeros(num_classes, dtype=np.int64)
    with torch.no_grad():
        for x, y in loader:
            x, y = x.to(device, non_blocking=True), y.to(device, non_blocking=True)
            pred = model(x).argmax(1)
            for c in range(num_classes):
                m = (y == c)
                total[c] += m.sum().item()
                correct[c] += ((pred == c) & m).sum().item()
    acc = np.where(total > 0, correct / np.maximum(total, 1), 0.0)
    return acc, total


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
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=None)
    ap.add_argument("--weight-decay", type=float, default=5e-4)
    ap.add_argument("--data-dir", default="/tmp/cifar10_smoke")
    ap.add_argument("--out", default="/home/fuqingxu/cc-workspace/muon/results/robustness")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--milestones", nargs="+", type=int, default=[7, 9])
    ap.add_argument("--gamma", type=float, default=0.1)
    ap.add_argument("--dropout", type=float, default=0.2)
    ap.add_argument("--label-smoothing", type=float, default=0.0)
    ap.add_argument("--small-data", type=int, default=None,
                    help="Train on stratified N samples (e.g. 5000, 10000, 25000, 50000)")
    ap.add_argument("--label-noise", type=float, default=None,
                    help="Train with symmetric noise rate (e.g. 0.0, 0.1, 0.2, 0.4)")
    ap.add_argument("--long-tail", type=float, default=None,
                    help="Train on long-tail subset with max/min ratio (e.g. 10, 50)")
    ap.add_argument("--lt-n-max", type=int, default=5000,
                    help="Head-class size for long-tail (default 5000)")
    ap.add_argument("--tag", type=str, default="")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = True

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, test_loader, variant, n_train = get_loaders(args)
    print(f"[setup] variant={variant} n_train={n_train} optim={args.optimizer} "
          f"epochs={args.epochs} bs={args.batch_size}")

    os.makedirs(args.out, exist_ok=True)
    suffix = f"_{args.tag}" if args.tag else ""
    out_file = os.path.join(args.out, f"{args.optimizer}_{variant}{suffix}.jsonl")

    model = SmallCNN(dropout=args.dropout).to(device)
    default_lr = {"sgd": 0.1, "adamw": 3e-3, "muon": 0.02}[args.optimizer]
    lr = args.lr if args.lr is not None else default_lr
    print(f"[setup] lr={lr}")

    opts = make_optimizer(args.optimizer, model, lr, args.weight_decay)
    schedulers = [torch.optim.lr_scheduler.MultiStepLR(opt, args.milestones, gamma=args.gamma)
                  for opt in opts]

    # Identify "tail" classes for long-tail evaluation
    if args.long_tail is not None:
        base = ParquetCifar10(args.data_dir, train=True)
        labels_full = base.labels
        from collections import Counter
        class_counts = Counter(labels_full.tolist())
        sorted_classes = sorted(class_counts.keys(), key=lambda c: -class_counts[c])
        # tail = bottom 3 classes (lowest original counts)
        tail_classes = sorted_classes[-3:]
        head_classes = sorted_classes[:3]
        print(f"[setup] long-tail head_classes={head_classes} tail_classes={tail_classes}")
    else:
        tail_classes = head_classes = None

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
                "train_loss": tr_loss,
                "train_acc": tr_acc,
                "val_loss": te_loss,
                "val_acc": te_acc,
                "lr": opts[0].param_groups[0]["lr"],
                "elapsed_sec": elapsed,
            }
            # Per-class accuracy at last epoch only (cheap on 10k test)
            if epoch + 1 == args.epochs:
                pc_acc, pc_total = per_class_accuracy(model, test_loader, device)
                record["per_class_acc"] = pc_acc.tolist()
                record["per_class_total"] = pc_total.tolist()
                if tail_classes is not None:
                    record["tail_mean_acc"] = float(pc_acc[list(tail_classes)].mean())
                    record["head_mean_acc"] = float(pc_acc[list(head_classes)].mean())
            log.append(record)
            f.write(json.dumps(record) + "\n")
            f.flush()
            gap = te_loss - tr_loss
            extra = ""
            if "tail_mean_acc" in record:
                extra = f" tail={record['tail_mean_acc']:.3f} head={record['head_mean_acc']:.3f}"
            print(f"[ep {epoch+1:02d}/{args.epochs}] tr_loss={tr_loss:.4f} tr_acc={tr_acc:.4f} "
                  f"te_loss={te_loss:.4f} te_acc={te_acc:.4f} gap={gap:+.4f}"
                  f" ep_t={time.time()-ep_t:.1f}s t={elapsed:.1f}s{extra}")

    print(f"[done] variant={variant} best_va={max(r['val_acc'] for r in log):.4f} "
          f"-> {out_file}")


if __name__ == "__main__":
    main()
