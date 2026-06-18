"""Robustness dataset wrappers for CIFAR-10.

Three variants on top of ParquetCifar10:
  - SubsetDataset         — train on a stratified random subset of N samples.
  - SymmetricNoiseDataset — full set, with p% symmetric (uniform) label noise.
  - LongTailDataset       — class-imbalanced subset with max/min ratio `imb_ratio`.
                            Class counts follow the standard exponential decay
                            n_c = n_max * (1/imb_ratio) ** (c / (C-1)).
                            Classes are sorted by original count descending
                            so that the head class is the most common in the
                            original CIFAR-10 train set.
"""
import numpy as np
import torch
from torch.utils.data import Dataset

from parquet_ds import ParquetCifar10


class _View(Dataset):
    """Wrap an array of indices + labels over a base dataset."""

    def __init__(self, base, indices, labels):
        self.base = base
        self.indices = np.asarray(indices, dtype=np.int64)
        self.labels = np.asarray(labels, dtype=np.int64)

    def __len__(self):
        return len(self.indices)

    def __getitem__(self, i):
        img, _ = self.base[int(self.indices[i])]
        return img, int(self.labels[i])


def stratified_subset_indices(labels, n, rng):
    """Pick n samples stratified by class (equal per class then random fill)."""
    labels = np.asarray(labels)
    classes = np.unique(labels)
    per_class = n // len(classes)
    rem = n - per_class * len(classes)
    idxs = []
    for c in classes:
        c_idx = np.where(labels == c)[0]
        chosen = rng.choice(c_idx, size=per_class, replace=False)
        idxs.append(chosen)
    if rem > 0:
        rng2 = np.random.default_rng(rng.integers(0, 2**31 - 1))
        for c in rng2.choice(classes, size=rem, replace=False):
            c_idx = np.where(labels == c)[0]
            already = set(idxs[list(classes).tolist().index(c)].tolist())
            remaining = np.setdiff1d(c_idx, list(already))
            idxs[list(classes).tolist().index(c)] = np.concatenate(
                [idxs[list(classes).tolist().index(c)],
                 rng.choice(remaining, size=1, replace=False)])
    out = np.concatenate(idxs)
    rng.shuffle(out)
    return out


class SubsetDataset(_View):
    """Stratified random subset of N samples. Labels unchanged."""

    def __init__(self, base_parquet_dir, n, seed=42):
        base = ParquetCifar10(base_parquet_dir, train=True)
        rng = np.random.default_rng(seed)
        idxs = stratified_subset_indices(base.labels, n, rng)
        super().__init__(base, idxs, base.labels[idxs])


class SymmetricNoiseDataset(_View):
    """Full set, but `noise_p` of labels are flipped uniformly to a wrong class."""

    def __init__(self, base_parquet_dir, noise_p, seed=42):
        base = ParquetCifar10(base_parquet_dir, train=True)
        rng = np.random.default_rng(seed)
        labels = base.labels.copy()
        n = len(labels)
        n_flip = int(round(n * noise_p))
        flip_idx = rng.choice(n, size=n_flip, replace=False)
        for i in flip_idx:
            wrong = np.array([c for c in range(10) if c != labels[i]])
            labels[i] = int(rng.choice(wrong))
        super().__init__(base, np.arange(n), labels)


class LongTailDataset(_View):
    """Class-imbalanced subset. Class c has n_c samples:
            n_c = n_max * (1/imb_ratio) ** (rank / (C-1))
    where `rank` is the position in the descending-count ordering.
    `imb_ratio` = max_count / min_count.
    `keep_n_max` is the head class size (default 5000; smaller for harsher tails).
    """

    def __init__(self, base_parquet_dir, imb_ratio=10.0, keep_n_max=5000, seed=42):
        base = ParquetCifar10(base_parquet_dir, train=True)
        rng = np.random.default_rng(seed)
        labels = base.labels
        classes = np.unique(labels)
        C = len(classes)
        # Sort classes by descending count to pick "head" first.
        order = sorted(classes, key=lambda c: -int((labels == c).sum()))
        # Build (class, n_c) pairs
        class_n = []
        for k, c in enumerate(order):
            n_c = int(round(keep_n_max * (1.0 / imb_ratio) ** (k / (C - 1))))
            class_n.append((c, max(n_c, 1)))
        # Sample per class
        per_class_idxs, per_class_lbls = [], []
        for c, n_c in class_n:
            c_idx = np.where(labels == c)[0]
            chosen = rng.choice(c_idx, size=n_c, replace=False)
            per_class_idxs.append(chosen)
            per_class_lbls.append(np.full(n_c, c, dtype=np.int64))
        idxs = np.concatenate(per_class_idxs)
        lbls = np.concatenate(per_class_lbls)
        order_perm = rng.permutation(len(idxs))
        super().__init__(base, idxs[order_perm], lbls[order_perm])


# --------------------------------------------------------------------------
# Test split helpers — keep test clean (no noise, no subset)
# --------------------------------------------------------------------------

class CleanTestDataset(Dataset):
    """Plain test split — wraps ParquetCifar10(train=False) directly."""

    def __init__(self, base_parquet_dir):
        self.base = ParquetCifar10(base_parquet_dir, train=False)

    def __len__(self):
        return len(self.base)

    def __getitem__(self, i):
        img, lbl = self.base[i]
        return img, int(lbl)