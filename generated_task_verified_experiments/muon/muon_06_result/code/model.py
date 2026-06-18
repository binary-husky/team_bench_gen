"""
Small CNN for CIFAR-10 — used as the architecture for our Muon reproduction.

A simple 6-conv-layer + 2-FC network (~1.5M params), chosen so that:
  - training is fast on a single A100 (a few minutes for 30 epochs)
  - it has clearly hidden 4D conv weights (perfect fit for Muon)
  - it has a 2D classifier head and 1D biases/norms (perfect for AdamW)
  - performance is meaningfully different between optimizers (no >97% saturation)

The architecture: 3 blocks of [3x3 conv -> 3x3 conv -> 2x2 max pool] with channels
[64, 128, 256], followed by a 2-layer MLP head. ~1.5M parameters.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


def conv3x3(in_c, out_c):
    return nn.Conv2d(in_c, out_c, kernel_size=3, padding=1, bias=False)


class BasicBlock(nn.Module):
    def __init__(self, in_c, out_c, stride=1):
        super().__init__()
        self.conv1 = conv3x3(in_c, out_c)
        self.bn1 = nn.BatchNorm2d(out_c)
        self.conv2 = conv3x3(out_c, out_c)
        self.bn2 = nn.BatchNorm2d(out_c)
        self.pool = nn.MaxPool2d(2) if stride == 2 else nn.Identity()
        if in_c != out_c or stride != 1:
            self.shortcut = nn.Sequential(
                nn.Conv2d(in_c, out_c, kernel_size=1, bias=False),
                nn.BatchNorm2d(out_c),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x):
        residual = self.shortcut(x)
        out = F.gelu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        out = out + residual
        out = F.gelu(out)
        out = self.pool(out)
        return out


class SmallCNN(nn.Module):
    """
    Hidden conv layers -> use Muon
    BN gains/biases, classifier head -> use AdamW

    width_factor: scales all hidden channels (stem, block1-3 widths, fc1 width).
                  width_factor=1.0 reproduces the original baseline (1.26M params).
                  width_factor=0.5 → ~0.32M params
                  width_factor=1.5 → ~2.84M params
                  width_factor=2.0 → ~5.04M params
    Channels are rounded to multiples of 8 for cuDNN efficiency.
    """

    def __init__(self, num_classes=10, dropout=0.2, width_factor=1.0):
        super().__init__()
        def w(b):
            return max(8, int(round(b * width_factor / 8) * 8))
        c1, c2, c3, c4 = w(64), w(128), w(256), w(512)
        fc1w = w(128)
        self.stem = conv3x3(3, c1)
        self.bn_stem = nn.BatchNorm2d(c1)
        self.block1 = BasicBlock(c1, c1, stride=2)   # 32 -> 16
        self.block2 = BasicBlock(c1, c2, stride=2)   # 16 -> 8
        self.block3 = BasicBlock(c2, c3, stride=2)   # 8 -> 4
        self.gap = nn.AdaptiveAvgPool2d(1)
        self.fc1 = nn.Linear(c3, fc1w)
        self.fc2 = nn.Linear(fc1w, num_classes)
        self.dropout = nn.Dropout(dropout)
        self.width_factor = width_factor

    def forward(self, x):
        x = F.gelu(self.bn_stem(self.stem(x)))
        x = self.block1(x)
        x = self.block2(x)
        x = self.block3(x)
        x = self.gap(x).flatten(1)
        x = F.gelu(self.fc1(x))
        x = self.dropout(x)
        return self.fc2(x)


def split_params_for_muon(model):
    """
    Return (muon_params, adamw_params) following Muon paper guidance:
      - Muon: hidden 2D+ weights (conv kernels reshaped, linear weights in hidden layers)
      - AdamW: 1D parameters (BN gain/bias), classifier head, embeddings
    """
    muon_params, adamw_params = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        # All conv kernels (4D) and hidden linear (2D, ndim>=2) -> Muon
        # Biases (1D), BN gain/bias (1D), and the final classifier head -> AdamW
        is_hidden = (
            (p.ndim >= 2)
            and ("fc2" not in name)
        )
        if is_hidden:
            muon_params.append(p)
        else:
            adamw_params.append(p)
    return muon_params, adamw_params


# Valid policy names
PARAM_POLICIES = ("hidden_2d", "no_first_conv", "conv_only", "all_2d", "no_shortcut")


def split_params_for_policy(model, policy):
    """
    Return (muon_params, adamw_params) for a given parameter-grouping policy.

    Policies:
      - hidden_2d    (baseline, paper): Muon: hidden 2D+ weights, AdamW: 1D + fc2
      - no_first_conv:                  Muon: hidden 2D+ except stem, AdamW: stem + 1D + fc2
      - conv_only:                      Muon: only 4D conv kernels, AdamW: fc1/fc2 + 1D
      - all_2d:                         Muon: all 2D+ including fc2, AdamW: only 1D
      - no_shortcut:                    Muon: stem + main path conv + fc1,
                                        AdamW: shortcut conv + 1D + fc2
    """
    if policy == "hidden_2d":
        return split_params_for_muon(model)

    muon_params, adamw_params = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        use_muon = False
        if policy == "no_first_conv":
            # Same as hidden_2d, but stem (first conv) goes to AdamW
            use_muon = (p.ndim >= 2) and ("fc2" not in name) and ("stem" not in name)
        elif policy == "conv_only":
            # Only conv kernels (4D); fc1 and fc2 both go to AdamW
            use_muon = p.ndim == 4
        elif policy == "all_2d":
            # All 2D+ tensors (including the output head fc2) -> Muon
            use_muon = p.ndim >= 2
        elif policy == "no_shortcut":
            # Main conv path + stem + fc1 -> Muon; shortcut conv + 1D + fc2 -> AdamW
            in_shortcut = "shortcut" in name
            use_muon = (p.ndim >= 2) and ("fc2" not in name) and (not in_shortcut)
        else:
            raise ValueError(f"Unknown policy: {policy}. Valid: {PARAM_POLICIES}")
        (muon_params if use_muon else adamw_params).append(p)
    return muon_params, adamw_params
