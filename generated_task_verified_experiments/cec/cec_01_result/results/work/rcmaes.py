"""Faithful Python/numpy port of RCMAES from the Minion framework
(github.com/khoirulmuzakka/Minion, minion/src/rcmaes.cpp).

Key facts recovered from the source:
  * Search is performed in the NORMALIZED box [0,1]^D; the objective is wrapped
    to denormalize back to the physical bounds. Hence sigma0 = 0.3 is in
    normalized units (= 0.3 * (UB-LB) in physical units).
  * Initial population N0 (lambda) follows eq. (6): with eta=Nmax/D>1e2 the
    multiplier is 10*log10(eta)-20, lambda = clamp(D*multiplier, lambda_min, 2000).
  * Nonlinear reduction exponent r = max(0.5, 1.7-0.01*D) (eq. 9).
  * Np(t) = lambda - (lambda - max(lambda_min,D)) * (1 - (1-t)^r), t=Nevals/Nmax.
  * Active CMA-ES core (Hansen tutorial parameters + active negative weights).
  * Restarts when (fmax-fmin)/|fmean| <= 1e-8; new mean sampled outside the
    per-dimension exclusion boxes (10% of [0,1]); sigma alternates 0.5*sigma0 /
    sigma0 between restarts.
  * Bound handling: "reflect-random" (resample near the violated bound within a
    width equal to the violation magnitude).
"""
import numpy as np


def enforce_bounds_reflect_random(X, lb=0.0, ub=1.0, rng=None):
    """Vectorized 'reflect-random' bound handling used by Minion."""
    if rng is None:
        rng = np.random
    X = X.copy()
    e = ub - lb
    low = X < lb
    if low.any():
        d_lower = np.abs(X[low] - lb)
        hr = lb + np.minimum(d_lower, e)
        X[low] = rng.uniform(0.0, 1.0, size=int(low.sum())) * (hr - lb) + lb
    high = X > ub
    if high.any():
        d_upper = np.abs(X[high] - ub)
        lr = ub - np.minimum(d_upper, e)
        X[high] = rng.uniform(0.0, 1.0, size=int(high.sum())) * (ub - lr) + lr
    return X


def _merged_intervals_1d(intervals):
    """Merge a list of (lo,hi) intervals; returns sorted merged list."""
    if not intervals:
        return []
    iv = sorted(intervals, key=lambda a: a[0])
    out = [list(iv[0])]
    for lo, hi in iv[1:]:
        if lo <= out[-1][1]:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [(a, b) for a, b in out]


def _sample_outside_local_bounds(lb, hi, local_bounds, rng):
    """Sample uniformly in [lb,hi] excluding the merged local_bounds intervals."""
    merged = _merged_intervals_1d(local_bounds)
    valid = []
    prev_hi = lb
    for lo, h in merged:
        if lo > prev_hi:
            valid.append((prev_hi, lo))
        prev_hi = min(h, hi)
    if prev_hi < hi:
        valid.append((prev_hi, hi))
    if not valid:
        return rng.uniform(lb, hi)
    lengths = np.array([b - a for a, b in valid])
    j = rng.choice(len(valid), p=lengths / lengths.sum())
    return rng.uniform(valid[j][0], valid[j][1])


def _compute_weights_and_params(lam, mu, dim):
    """Recompute active-CMA weights and Hansen-tutorial parameters.

    Mirrors RCMAES::Parameter::reinit/resize weight & parameter block.
    """
    i = np.arange(lam)
    w = np.log((lam + 1.0) / 2.0) - np.log(i + 1.0)
    w_pos_sum = w[w >= 0.0].sum()
    w_neg_sum = w[w < 0.0].sum()

    w_par = w[:mu]
    w_sum_par = w_par.sum()
    w_sq_par = (w_par * w_par).sum()
    mu_eff = (w_sum_par * w_sum_par) / max(w_sq_par, 1e-12)

    c_s = (mu_eff + 2.0) / (dim + mu_eff + 5.0)
    c_c = (4.0 + mu_eff / dim) / (dim + 4.0 + 2.0 * mu_eff / dim)
    c_1 = 2.0 / ((dim + 1.3) ** 2 + mu_eff)
    c_mu = 2.0 * (mu_eff - 2.0 + 1.0 / mu_eff) / ((dim + 2.0) ** 2 + mu_eff)
    c_mu = min(1.0 - c_1, c_mu)
    d_s = 1.0 + c_s + 2.0 * max(0.0, np.sqrt((mu_eff - 1.0) / (dim + 1.0)) - 1.0)
    chi = np.sqrt(dim) * (1.0 - 1.0 / (4.0 * dim) + 1.0 / (21.0 * dim * dim))
    p_s_fact = np.sqrt(c_s * (2.0 - c_s) * mu_eff)
    p_c_fact = np.sqrt(c_c * (2.0 - c_c) * mu_eff)

    a_mu = 1.0 + c_1 / max(c_mu, 1e-12)
    a_mueff = 1.0 + 2.0 * mu_eff
    a_posdef = (1.0 - c_1 - c_mu) / (dim * max(c_mu, 1e-12))
    a_min = min(a_mu, a_mueff, a_posdef)

    w_norm = w.copy()
    pos = w >= 0.0
    w_norm[pos] = w[pos] / max(w_pos_sum, 1e-12)
    w_norm[~pos] = a_min * w[~pos] / max(abs(w_neg_sum), 1e-12)

    return dict(w=w_norm, mu_eff=mu_eff, c_s=c_s, c_c=c_c, c_1=c_1, c_mu=c_mu,
                d_s=d_s, chi=chi, p_s_fact=p_s_fact, p_c_fact=p_c_fact)


class _Era:
    """Holds the mutable CMA-ES state for one 'era' (between restarts)."""

    def __init__(self, dim):
        self.dim = dim
        self.reset_state()

    def reset_state(self):
        d = self.dim
        self.x_mean = np.zeros(d)
        self.sigma = 0.3
        self.C = np.eye(d)
        self.B = np.eye(d)
        self.D = np.eye(d)            # diag(sqrt(eigvals))
        self.C_invsqrt = np.eye(d)    # B diag(1/sqrt(eig)) B^T
        self.p_s = np.zeros(d)
        self.p_c = np.zeros(d)
        self.i_iteration = 0
        self.params = None

    def reinit(self, lam, mu, x_mean, sigma):
        self.params = _compute_weights_and_params(lam, mu, self.dim)
        self.x_mean = x_mean.copy()
        self.sigma = sigma
        d = self.dim
        self.C = np.eye(d)
        self.B = np.eye(d)
        self.D = np.eye(d)
        self.C_invsqrt = np.eye(d)
        self.p_s = np.zeros(d)
        self.p_c = np.zeros(d)
        self.i_iteration = 0

    def resize(self, lam, mu):
        self.params = _compute_weights_and_params(lam, mu, self.dim)


def rcmaes_minimize(func_norm, dim, maxevals, seed=0, sigma0=0.3):
    """Minimize a (normalized) objective over [0,1]^dim.

    func_norm(X) takes an (n, dim) array of points in [0,1] and returns (n,)
    objective values (in physical units). Returns (best_x_physical, best_f,
    best_x_norm, nevals).

    Physical bounds are fixed to the CEC2022 box [-100,100].
    """
    rng = np.random.RandomState(seed)
    LB, UB = -100.0, 100.0

    def denorm(Xn):
        return LB + Xn * (UB - LB)

    def evaluate(Xn):
        return np.asarray(func_norm(Xn), dtype=np.float64)

    dim = int(dim)
    lambda_min = max(int(np.ceil(4.0 + 3.0 * np.log(dim))), 4)
    eta = float(maxevals) / float(dim)
    logeta = np.log10(eta)
    multiplier = 10.0 * logeta - 20.0 if logeta > 2.0 else 2.0
    lam0 = int(np.clip(dim * multiplier, lambda_min, 2000.0))
    lam0 = min(2000, max(lam0, 4))
    mu_ratio = 0.5
    mu0 = max(int(np.ceil(mu_ratio * lam0)), 1)
    r = max(0.5, 1.7 - 0.01 * dim)

    era = _Era(dim)
    Nevals = 0
    best_x = None
    best_f = np.inf
    sigma_eff = sigma0
    lam_cur = lam0
    mu_cur = mu0
    A = float(lam0)
    Cmin = float(max(lambda_min, dim))

    initial_mean = rng.uniform(0.0, 1.0, size=dim)
    era.reinit(lam_cur, mu_cur, initial_mean, sigma_eff)
    use_lhs = False
    lhs_x = None

    while Nevals < maxevals:
        # --- nonlinear population-size reduction ---
        t = min(1.0, Nevals / float(maxevals))
        value = A - (A - Cmin) * (1.0 - (1.0 - t) ** r)
        lam_target = int(round(value))
        lam_target = max(lam_target, lambda_min, 4)
        if lam_target != lam_cur:
            lam_cur = lam_target
            mu_cur = max(1, min(lam_cur, int(round(mu_ratio * lam_cur))))
            era.resize(lam_cur, mu_cur)

        w = era.params["w"]
        c_s, c_c, c_1, c_mu = era.params["c_s"], era.params["c_c"], era.params["c_1"], era.params["c_mu"]
        d_s, chi = era.params["d_s"], era.params["chi"]
        p_s_fact, p_c_fact = era.params["p_s_fact"], era.params["p_c_fact"]

        # --- sample offspring ---
        BD = era.B @ era.D
        z = rng.standard_normal((dim, lam_cur))
        y = BD @ z                                   # (dim, lam)
        x = era.x_mean[:, None] + era.sigma * y      # normalized coords
        x = enforce_bounds_reflect_random(x.T, 0.0, 1.0, rng).T   # (dim, lam)
        y = (x - era.x_mean[:, None]) / era.sigma    # recompute y from bounded x

        if use_lhs:
            # first generation of a restart uses the pre-sampled population
            xl = np.asarray(lhs_x).T  # (dim, lam)
            xl = enforce_bounds_reflect_random(xl.T, 0.0, 1.0, rng).T
            x = xl
            y = (x - era.x_mean[:, None]) / era.sigma
            use_lhs = False

        # --- evaluate (with budget cap) ---
        if Nevals >= maxevals:
            break
        remaining = maxevals - Nevals
        evalCount = min(remaining, lam_cur)
        if evalCount <= 0:
            break
        fvals = evaluate(denorm(x[:, :evalCount].T))
        f = np.full(lam_cur, np.inf)
        f[:evalCount] = np.where(np.isnan(fvals), np.inf, fvals)
        Nevals += evalCount

        # --- rank & sort ---
        order = np.argsort(f, kind="stable")         # ascending
        y_ranked = y[:, order]
        # w_var starts as w; negatives updated below
        w_var = w.copy()

        # --- update best ---
        bi = order[0]
        if np.isfinite(f[bi]) and f[bi] < best_f:
            best_f = f[bi]
            best_x = x[:, bi].copy()

        # --- assign new mean ---
        y_mean = y_ranked[:, :mu_cur] @ w[:mu_cur]
        era.x_mean = era.x_mean + era.sigma * y_mean

        # --- evolution paths ---
        CinvSqrt_y = era.C_invsqrt @ y_mean
        era.p_s = (1.0 - c_s) * era.p_s + p_s_fact * CinvSqrt_y
        norm_ps = np.linalg.norm(era.p_s)
        thr = (1.4 + 2.0 / (dim + 1.0)) * np.sqrt(max(0.0, 1.0 - (1.0 - c_s) ** (2.0 * (era.i_iteration + 1)))) * chi
        h_sig = norm_ps < thr
        era.p_c = (1.0 - c_c) * era.p_c + (p_c_fact if h_sig else 0.0) * y_mean

        # --- active negative weights (vectorized) ---
        neg = w < 0.0
        if neg.any():
            Yn = y_ranked[:, neg]                    # (dim, n_neg)
            adj = era.C_invsqrt @ Yn
            denom = np.einsum("ij,ij->j", adj, adj)
            wv = np.zeros_like(denom)
            nz = denom > 0.0
            wv[nz] = w[neg][nz] * dim / denom[nz]
            w_var[neg] = wv

        # --- covariance update ---
        h1 = (1.0 - h_sig) * c_c * (2.0 - c_c)
        w_sum = w.sum()
        Yr = y_ranked[:, :lam_cur]
        yWeighted = (Yr * w_var[:lam_cur]) @ Yr.T
        era.C = (1.0 + c_1 * h1 - c_1 - c_mu * w_sum) * era.C + c_1 * np.outer(era.p_c, era.p_c) + c_mu * yWeighted
        era.C = 0.5 * (era.C + era.C.T)

        # --- eigendecomposition ---
        try:
            ev, B = np.linalg.eigh(era.C)
        except np.linalg.LinAlgError:
            ev = np.ones(dim)
            B = np.eye(dim)
        ev = np.maximum(ev, 1e-30)
        era.B = B
        era.D = np.diag(np.sqrt(ev))
        era.C_invsqrt = (B * (1.0 / np.sqrt(ev))) @ B.T

        # --- step-size update ---
        era.sigma *= np.exp((c_s / d_s) * (norm_ps / chi - 1.0))

        # --- convergence / restart test ---
        fmax, fmin = f.max(), f.min()
        fmean = f.mean()
        rel_range = (fmax - fmin) / abs(fmean) if abs(fmean) > 1e-12 else 0.0
        era.i_iteration += 1

        if rel_range < 1e-8:
            # build per-dimension exclusion boxes around current best
            locals_per_dim = [[] for _ in range(dim)]
            for bx in ([best_x] if best_x is not None else []):
                for d in range(dim):
                    lo = max(0.0, bx[d] - 0.1)
                    hi_ = min(1.0, bx[d] + 0.1)
                    locals_per_dim[d].append((lo, hi_))
            # sample a new population outside all exclusion boxes
            new_pop = np.empty((lam_cur, dim))
            for j in range(lam_cur):
                for d in range(dim):
                    new_pop[j, d] = _sample_outside_local_bounds(0.0, 1.0, locals_per_dim[d], rng)
            new_mean = new_pop.mean(axis=0)
            sigma_eff = 0.5 * sigma0 if sigma_eff == sigma0 else sigma0
            era.reinit(lam_cur, mu_cur, new_mean, sigma_eff)
            lhs_x = new_pop
            use_lhs = True

    if best_x is None:
        return None, best_f, None, Nevals
    return denorm(best_x[None, :])[0], best_f, best_x, Nevals


# ---- convenience wrapper that closes over a CEC2022 function number ----
def make_rcmaes_objective(cec_eval_batch, func_num):
    """cec_eval_batch(X_phys, func_num) -> values. Returns a normalized objective."""
    def obj(Xn):
        LB, UB = -100.0, 100.0
        Xp = LB + Xn * (UB - LB)
        return cec_eval_batch(Xp, func_num)
    return obj
