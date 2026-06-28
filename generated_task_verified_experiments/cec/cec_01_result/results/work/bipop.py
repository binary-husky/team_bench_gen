"""Faithful Python/numpy port of BIPOP-aCMAES from the Minion framework
(minion/src/bipop_acmaes.cpp). Unlike RCMAES, BIPOP-aCMAES operates in the
PHYSICAL search box [-100,100] (sigma0 = 0.3 * avg_range = 60), uses a fixed
population per regime, and restarts with the classic BIPOP strategy: alternating
IPOP (doubling) large-population restarts and random small-population restarts
from the best point, until the budget is exhausted. The per-generation active
CMA-ES update is identical to RCMAES.
"""
import numpy as np
from rcmaes import _Era, _compute_weights_and_params, enforce_bounds_reflect_random

LB, UB = -100.0, 100.0


def _stopping_criteria(era, sigma0):
    """Replicate BIPOP_aCMAES::checkStoppingCriteria. Returns True if regime should end."""
    eigvals = era.eigvals
    emin = max(eigvals.min(), 1e-30)
    emax = eigvals.max()
    if emax / emin > 1e14:
        return True
    sigma_fac = era.sigma / sigma0 if sigma0 > 0 else era.sigma
    if sigma_fac > 1e20 * np.sqrt(emax):
        return True
    # principal-axis no-movement
    for i in range(era.dim):
        axis = (0.1 * era.sigma * eigvals[i]) * era.B[:, i]
        moved = era.x_mean + axis
        if np.all(moved == era.x_mean):
            return True
    # coordinate no-movement
    for i in range(era.dim):
        delta = 0.2 * era.sigma * np.sqrt(era.C[i, i])
        if era.x_mean[i] + delta == era.x_mean[i]:
            return True
    return False


class _BipEra(_Era):
    def reset_state(self):
        super().reset_state()
        self.eigvals = np.ones(self.dim)

    def reinit(self, lam, mu, x_mean, sigma):
        self.params = _compute_weights_and_params(lam, mu, self.dim)
        self.x_mean = x_mean.copy()
        self.sigma = sigma
        d = self.dim
        self.C = np.eye(d)
        self.B = np.eye(d)
        self.D = np.eye(d)
        self.C_invsqrt = np.eye(d)
        self.eigvals = np.ones(d)
        self.p_s = np.zeros(d)
        self.p_c = np.zeros(d)
        self.i_iteration = 0


def bipop_minimize(func_phys, dim, maxevals, seed=0, sigma0_frac=0.3, max_iter=5000):
    """BIPOP-aCMAES on physical [-100,100]^dim. func_phys(X) -> values for (n,dim)."""
    rng = np.random.RandomState(seed)
    avg_range = UB - LB
    sigma0 = sigma0_frac * avg_range
    logDim = np.log(dim)
    lambda0 = max(int(4.0 + np.floor(3.0 * logDim)), 4)
    mu0 = max(lambda0 // 2, 1)

    era = _BipEra(dim)
    Nevals = 0
    best_x = None
    best_f = np.inf
    initial_mean = rng.uniform(LB, UB, size=dim)

    def evaluate(X):
        return np.asarray(func_phys(X), dtype=np.float64)

    def run_regime(start_mean, start_sigma, lam):
        nonlocal Nevals, best_x, best_f
        mu = max(lam // 2, 1)
        era.reinit(lam, mu, start_mean, start_sigma)
        stop_opt = False
        while era.i_iteration < max_iter and not stop_opt:
            w = era.params["w"]
            c_s, c_c, c_1, c_mu = era.params["c_s"], era.params["c_c"], era.params["c_1"], era.params["c_mu"]
            d_s, chi = era.params["d_s"], era.params["chi"]
            p_s_fact, p_c_fact = era.params["p_s_fact"], era.params["p_c_fact"]

            BD = era.B @ era.D
            z = rng.standard_normal((dim, lam))
            y = BD @ z
            x = era.x_mean[:, None] + era.sigma * y
            x = enforce_bounds_reflect_random(x.T, LB, UB, rng).T
            y = (x - era.x_mean[:, None]) / era.sigma

            if Nevals >= maxevals:
                stop_opt = True
                break
            remaining = maxevals - Nevals
            evalCount = min(remaining, lam)
            if evalCount <= 0:
                stop_opt = True
                break
            fvals = evaluate(x[:, :evalCount].T)
            f = np.full(lam, np.inf)
            f[:evalCount] = np.where(np.isnan(fvals), np.inf, fvals)
            Nevals += evalCount
            if evalCount < lam:
                stop_opt = True  # budget exhausted within regime

            order = np.argsort(f, kind="stable")
            y_ranked = y[:, order]
            w_var = w.copy()

            bi = order[0]
            if np.isfinite(f[bi]) and f[bi] < best_f:
                best_f = f[bi]
                best_x = x[:, bi].copy()

            y_mean = y_ranked[:, :mu] @ w[:mu]
            era.x_mean = era.x_mean + era.sigma * y_mean

            CinvSqrt_y = era.C_invsqrt @ y_mean
            era.p_s = (1.0 - c_s) * era.p_s + p_s_fact * CinvSqrt_y
            norm_ps = np.linalg.norm(era.p_s)
            thr = (1.4 + 2.0 / (dim + 1.0)) * np.sqrt(max(0.0, 1.0 - (1.0 - c_s) ** (2.0 * (era.i_iteration + 1)))) * chi
            h_sig = norm_ps < thr
            era.p_c = (1.0 - c_c) * era.p_c + (p_c_fact if h_sig else 0.0) * y_mean

            neg = w < 0.0
            if neg.any():
                Yn = y_ranked[:, neg]
                adj = era.C_invsqrt @ Yn
                denom = np.einsum("ij,ij->j", adj, adj)
                wv = np.zeros_like(denom)
                nz = denom > 0.0
                wv[nz] = w[neg][nz] * dim / denom[nz]
                w_var[neg] = wv

            h1 = (1.0 - h_sig) * c_c * (2.0 - c_c)
            w_sum = w.sum()
            Yr = y_ranked[:, :lam]
            yWeighted = (Yr * w_var[:lam]) @ Yr.T
            era.C = (1.0 + c_1 * h1 - c_1 - c_mu * w_sum) * era.C + c_1 * np.outer(era.p_c, era.p_c) + c_mu * yWeighted
            era.C = 0.5 * (era.C + era.C.T)

            try:
                ev, B = np.linalg.eigh(era.C)
            except np.linalg.LinAlgError:
                ev, B = np.ones(dim), np.eye(dim)
            ev = np.maximum(ev, 1e-30)
            era.B = B
            era.D = np.diag(np.sqrt(ev))
            era.C_invsqrt = (B * (1.0 / np.sqrt(ev))) @ B.T
            era.eigvals = ev

            era.sigma *= np.exp((c_s / d_s) * (norm_ps / chi - 1.0))

            era.i_iteration += 1
            if _stopping_criteria(era, sigma0):
                break
        return Nevals

    budget_large = run_regime(initial_mean, sigma0, lambda0)
    restart = 1
    while Nevals < maxevals:
        lambda_large = lambda0 * (1 << restart) if restart < (8 * 64) else np.iinfo(np.int64).max // 2
        lambda_large = min(lambda_large, maxevals)
        budget_small = 0
        while budget_large > budget_small and Nevals < maxevals:
            u1 = rng.uniform(0.0, 1.0)
            u2 = rng.uniform(0.0, 1.0)
            lambda_small = max(int(round(lambda0 * (0.5 * lambda_large / lambda0) ** (u1 * u1))), 4)
            sigma_small = sigma0 * 2.0 * (10.0 ** (-2.0 * u2))
            before = Nevals
            run_regime(best_x if best_x is not None else initial_mean, sigma_small, lambda_small)
            budget_small += Nevals - before
        if Nevals >= maxevals:
            break
        before = Nevals
        run_regime(initial_mean, sigma0, lambda_large)
        budget_large += Nevals - before
        restart += 1

    return best_x, best_f, Nevals
