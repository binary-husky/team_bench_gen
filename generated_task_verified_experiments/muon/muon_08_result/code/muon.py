"""
Muon optimizer - single-device version, faithful to Keller Jordan's 2024 paper.

Algorithm:
  1. Maintain momentum buffer m (SGD-momentum with Nesterov)
  2. Apply Newton-Schulz quintic iteration to compute orthogonalized update O
  3. Scale O by some factor (depends on update_scaling mode)
  4. p <- (1 - lr*wd) * p - lr * scaled_O

Update scaling modes:
  - paper:           sqrt(max(1, rows/cols))  -- Muon paper default
  - none:            1.0                       -- no rescaling
  - sqrt_rows_cols:  sqrt(rows/cols)           -- symmetric, allows < 1 for tall
  - rms_match:       rms(buf) / rms(O)         -- match the original momentum RMS
  - spectral_clip:   cap ||O||_2 to max_norm   -- default max_norm = 1.0

Reference: https://kellerjordan.github.io/posts/muon/
"""
import torch


@torch.no_grad()
def zeropower_via_newtonschulz5(G, steps=5, eps=1e-7, abc=(3.4445, -4.7750, 2.0315)):
    """
    Newton-Schulz quintic iteration for zeroth-power / orthogonalization.

    Three coefficient sets considered:
      (3.4445, -4.7750, 2.0315)  - Jordan 2024: maximize slope at zero (3.44)
                                  -> not exact orthogonalization; S_ii ~ U(0.5, 1.5)
      (3.0, -3.0, 2.0)           - naive symmetric cubic-like coefficients
                                  -> p(1)=2 (overshoots singular values > 1)
      (1.875, -1.25, 0.375)      - classical coefficients: p(1)=1, p'(1)=0
                                  -> true orthogonalization but slower (slope=1.875)
    """
    assert G.ndim >= 2
    a, b, c = abc
    X = G.to(torch.bfloat16)
    if X.size(-2) > X.size(-1):
        X = X.mT
    # Normalize so spectral norm is at most 1.
    X = X / (X.norm(dim=(-2, -1), keepdim=True) + eps)
    for _ in range(steps):
        A = X @ X.mT
        B = b * A + c * (A @ A)
        X = a * X + B @ X
    if G.size(-2) > G.size(-1):
        X = X.mT
    return X.to(G.dtype)


def compute_update_scale(update, mode, original_momentum=None, max_norm=1.0):
    """
    Compute the scaling factor for the Newton-Schulz output.

    update:                the NS-orthogonalized update, shape (rows, cols)
    mode:                  one of {'paper', 'none', 'sqrt_rows_cols',
                                  'rms_match', 'spectral_clip'}
    original_momentum:     the pre-NS momentum buf (needed for rms_match)
    max_norm:              the upper bound for spectral_clip (default 1.0)

    Returns: scalar tensor on the same device as update.
    """
    rows, cols = update.size(-2), update.size(-1)
    if mode == "paper":
        # Muon paper: only scale up if rows > cols (wide layer)
        return max(1.0, rows / cols) ** 0.5
    elif mode == "none":
        return torch.tensor(1.0, device=update.device, dtype=update.dtype)
    elif mode == "sqrt_rows_cols":
        # Symmetric: sqrt(rows/cols); for tall layers (rows<cols) this is < 1
        return (rows / cols) ** 0.5
    elif mode == "rms_match":
        # Match the per-element RMS of the original (pre-NS) momentum
        if original_momentum is None:
            raise ValueError("rms_match requires original_momentum")
        u_rms = update.pow(2).mean().sqrt()
        m_rms = original_momentum.pow(2).mean().sqrt()
        # Avoid div-by-zero
        return (m_rms / (u_rms + 1e-12))
    elif mode == "spectral_clip":
        # Cap the spectral norm to max_norm. Compute sigma_2 (largest singular
        # value) of the orthogonalized update; if > max_norm, rescale down.
        # For our NS output, sigma_2 is ~1.0 already, so this is mostly a no-op
        # except when combined with the rows/cols geometry.
        sigma = torch.linalg.matrix_norm(update.float(), ord=2)
        scale = (max_norm / (sigma + 1e-12)).clamp(max=1.0)
        return scale
    else:
        raise ValueError(f"Unknown update_scaling: {mode!r}")


class Muon(torch.optim.Optimizer):
    """
    Single-device Muon optimizer.
    Use only for 2D+ hidden weights. Use AdamW for embeddings, head, biases, norms.
    """

    def __init__(self, params, lr=0.02, momentum=0.95, nesterov=True,
                 weight_decay=0.0, ns_steps=5, ns_abc=(3.4445, -4.7750, 2.0315),
                 update_scaling="paper", spectral_max_norm=1.0):
        if lr < 0.0:
            raise ValueError(f"Invalid lr: {lr}")
        valid = ("paper", "none", "sqrt_rows_cols", "rms_match", "spectral_clip")
        if update_scaling not in valid:
            raise ValueError(f"Invalid update_scaling: {update_scaling!r}; "
                             f"valid: {valid}")
        defaults = dict(lr=lr, momentum=momentum, nesterov=nesterov,
                        weight_decay=weight_decay, ns_steps=ns_steps, ns_abc=ns_abc,
                        update_scaling=update_scaling,
                        spectral_max_norm=spectral_max_norm)
        super().__init__(params, defaults)

    @torch.no_grad()
    def step(self, closure=None):
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()
        for group in self.param_groups:
            lr = group["lr"]
            wd = group["weight_decay"]
            momentum = group["momentum"]
            nesterov = group["nesterov"]
            ns_steps = group["ns_steps"]
            ns_abc = group["ns_abc"]
            scaling = group["update_scaling"]
            max_norm = group["spectral_max_norm"]
            for p in group["params"]:
                if p.grad is None:
                    continue
                g = p.grad
                state = self.state[p]
                if "momentum_buffer" not in state:
                    state["momentum_buffer"] = torch.zeros_like(g)
                buf = state["momentum_buffer"]
                # Heavy-ball momentum
                buf.mul_(momentum).add_(g)
                # Nesterov
                g_eff = g.add(buf, alpha=momentum) if nesterov else buf
                # Snapshot pre-NS momentum (for rms_match). Use g_eff as
                # the canonical "raw momentum" (buf for heavy-ball,
                # g + momentum*buf for Nesterov — same as applied to NS).
                raw_momentum_2d = g_eff

                # Reshape conv filters (4D) to 2D
                orig_shape = g_eff.shape
                if g_eff.ndim == 4:
                    g_eff_2d = g_eff.view(g_eff.size(0), -1)
                    raw_momentum_2d = raw_momentum_2d.view(raw_momentum_2d.size(0), -1)
                else:
                    g_eff_2d = g_eff

                update = zeropower_via_newtonschulz5(g_eff_2d, steps=ns_steps, abc=ns_abc)

                # Compute scaling factor for this update
                scale = compute_update_scale(
                    update, scaling,
                    original_momentum=raw_momentum_2d if scaling == "rms_match" else None,
                    max_norm=max_norm,
                )
                update = update * scale
                update = update.view(orig_shape)

                # Weight decay (decoupled, AdamW-style)
                if wd != 0:
                    p.data.mul_(1.0 - lr * wd)
                p.data.add_(update, alpha=-lr)
        return loss
