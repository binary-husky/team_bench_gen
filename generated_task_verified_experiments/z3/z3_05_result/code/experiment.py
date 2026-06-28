#!/usr/bin/env python3
"""
Compare z3 satisfiability (Solver, sat) vs optimization (Optimize, minimize).

Problem: small job-shop scheduling -- minimize makespan.
- n jobs, m machines.
- Each job j has a fixed sequence of m operations; operation (j,k) runs on
  machine route[j][k] with duration dur[j][k].
- Decision vars: start times s[j][k] (integer >= 0).
- Precedence within a job: s[j][k+1] >= s[j][k] + dur[j][k].
- No-overlap on each machine: pairwise disjunctive (either before or after).
- Objective: makespan = max over (j,k) of (s[j][k] + dur[j][k]).

Fixed instance; the independent variable is solving mode (sat vs optimize).
"""
import time
import statistics
import z3

# ---- Fixed instance (job-shop, 5 jobs x 4 machines) ----
JOBS = [
    # (route: machine index per step, duration per step)
    ([0, 1, 2, 3], [3, 4, 7, 2]),
    ([1, 0, 3, 2], [6, 5, 4, 3]),
    ([2, 3, 1, 0], [2, 4, 6, 4]),
    ([3, 2, 0, 1], [5, 3, 4, 5]),
    ([0, 3, 2, 1], [4, 6, 3, 4]),
]
N_JOBS = len(JOBS)
N_MAC = 4

def build_vars():
    s = [[z3.Int(f"s_{j}_{k}") for k in range(len(JOBS[j][0]))] for j in range(N_JOBS)]
    makespan = z3.Int("makespan")
    return s, makespan

def base_constraints(s, makespan):
    c = []
    for j in range(N_JOBS):
        route, dur = JOBS[j]
        for k in range(len(route)):
            c.append(s[j][k] >= 0)
            c.append(makespan >= s[j][k] + dur[k])
            if k + 1 < len(route):
                c.append(s[j][k+1] >= s[j][k] + dur[k])
        # no-overlap on each machine: for any two ops on same machine
    # pairwise disjunction per machine
    # collect ops per machine
    ops_by_mac = {m: [] for m in range(N_MAC)}
    for j in range(N_JOBS):
        route, dur = JOBS[j]
        for k in range(len(route)):
            ops_by_mac[route[k]].append((j, k, dur[k]))
    for m in range(N_MAC):
        ops = ops_by_mac[m]
        for a in range(len(ops)):
            for b in range(a+1, len(ops)):
                j1,k1,d1 = ops[a]
                j2,k2,d2 = ops[b]
                # s1+d1 <= s2  OR  s2+d2 <= s1
                c.append(z3.Or(s[j1][k1]+d1 <= s[j2][k2],
                               s[j2][k2]+d2 <= s[j1][k1]))
    return c

def get_makespan_value(s, makespan, model):
    vals = []
    for j in range(N_JOBS):
        route, dur = JOBS[j]
        for k in range(len(route)):
            vals.append(model.eval(s[j][k]).as_long() + dur[k])
    ms_model = model.eval(makespan).as_long()
    return max(vals), ms_model

def run_sat():
    """Find one feasible solution with plain Solver (sat)."""
    s, makespan = build_vars()
    slv = z3.Solver()
    for c in base_constraints(s, makespan):
        slv.add(c)
    # bound makespan so the model is forced to assign something concrete,
    # but large enough to be easily satisfiable (loose bound -> quick sat)
    slv.add(makespan >= 0)
    t0 = time.perf_counter()
    res = slv.check()
    t1 = time.perf_counter()
    assert res == z3.sat, res
    m = slv.model()
    true_ms, declared_ms = get_makespan_value(s, makespan, m)
    return t1 - t0, true_ms, declared_ms, m

def run_optimize():
    """Find optimal makespan with Optimize (minimize)."""
    s, makespan = build_vars()
    opt = z3.Optimize()
    for c in base_constraints(s, makespan):
        opt.add(c)
    t0 = time.perf_counter()
    h = opt.minimize(makespan)
    res = opt.check()
    t1 = time.perf_counter()
    assert res == z3.sat, res
    m = opt.model()
    true_ms, declared_ms = get_makespan_value(s, makespan, m)
    opt_val = m.eval(makespan).as_long()
    return t1 - t0, true_ms, declared_ms, opt_val, m

def main():
    print("z3 version:", z3.get_version_string())
    # Warm up + repeat for stable timing
    REPS = 7

    sat_times = []
    sat_true = None
    sat_dec = None
    for _ in range(REPS):
        dt, tms, dms, _ = run_sat()
        sat_times.append(dt)
        sat_true, sat_dec = tms, dms
    # first call includes import/jit warmup; report median of all and also
    # median excluding the very first warm-up call
    sat_med = statistics.median(sat_times)
    sat_med_warm = statistics.median(sat_times[1:])

    opt_times = []
    opt_true = None
    opt_val = None
    for _ in range(REPS):
        dt, tms, dms, oval, _ = run_optimize()
        opt_times.append(dt)
        opt_true, opt_val = tms, oval
    opt_med = statistics.median(opt_times)
    opt_med_warm = statistics.median(opt_times[1:])

    print("=== SAT (feasible) ===")
    print("  times (s):", [round(x,4) for x in sat_times])
    print("  median: %.4f  median(warm): %.4f" % (sat_med, sat_med_warm))
    print("  feasible makespan (computed):", sat_true, " declared:", sat_dec)
    print("=== OPTIMIZE (minimize) ===")
    print("  times (s):", [round(x,4) for x in opt_times])
    print("  median: %.4f  median(warm): %.4f" % (opt_med, opt_med_warm))
    print("  optimal makespan (computed):", opt_true, " objective:", opt_val)
    print("=== RATIO ===")
    print("  objective gap feasible vs optimal:", sat_true, "vs", opt_true,
          " -> feasible is %.2fx optimal" % (sat_true/opt_val))
    print("  time ratio optimize/sat (warm med): %.2fx" % (opt_med_warm/sat_med_warm))

    # write machine-readable summary line
    with open("results.txt", "w") as f:
        f.write(f"sat_time_median_warm={sat_med_warm:.6f}\n")
        f.write(f"opt_time_median_warm={opt_med_warm:.6f}\n")
        f.write(f"sat_feasible_makespan={sat_true}\n")
        f.write(f"opt_optimal_makespan={opt_val}\n")
        f.write(f"sat_times={[round(x,6) for x in sat_times]}\n")
        f.write(f"opt_times={[round(x,6) for x in opt_times]}\n")

if __name__ == "__main__":
    main()
