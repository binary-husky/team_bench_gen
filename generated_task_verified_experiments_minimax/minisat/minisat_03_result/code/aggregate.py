import csv
import statistics
from collections import defaultdict

rows = list(csv.DictReader(open('/data/workspace/admin/happy_lake/.verify_judge_minimax/minisat/minisat_03/results_full.csv')))
for r in rows:
    r['n'] = int(r['n'])
    r['m'] = int(r['m'])
    r['seed'] = int(r['seed'])
    r['dpll_decisions'] = int(r['dpll_decisions'])
    r['cdcl_decisions'] = int(r['cdcl_decisions'])
    r['dpll_conflicts'] = int(r['dpll_conflicts'])
    r['cdcl_conflicts'] = int(r['cdcl_conflicts'])
    r['dpll_time'] = float(r['dpll_time'])
    r['cdcl_time'] = float(r['cdcl_time'])
    r['dpll_propagations'] = int(r['dpll_propagations'])
    r['cdcl_propagations'] = int(r['cdcl_propagations'])
    r['dpll_max_depth'] = int(r['dpll_max_depth'])
    r['cdcl_restarts'] = int(r['cdcl_restarts'])

by_n = defaultdict(list)
for r in rows:
    by_n[r['n']].append(r)

print("n    N   #TO   #SAT   #UNS   DPLL dec mean/med   CDCL dec mean/med   DPLL time mean/med   CDCL time mean/med   ratio_dec   ratio_time")
for n in sorted(by_n):
    rs = by_n[n]
    d_dec = [r['dpll_decisions'] for r in rs]
    c_dec = [r['cdcl_decisions'] for r in rs]
    d_t = [r['dpll_time'] for r in rs]
    c_t = [r['cdcl_time'] for r in rs]
    n_to = sum(1 for r in rs if r['dpll_status'] == 'timeout')
    n_sat = sum(1 for r in rs if r['cdcl_status'] == 'sat')
    n_uns = sum(1 for r in rs if r['cdcl_status'] == 'unsat')
    mean_d = statistics.mean(d_dec)
    mean_c = statistics.mean(c_dec)
    mean_dt = statistics.mean(d_t)
    mean_ct = statistics.mean(c_t)
    med_d = statistics.median(d_dec)
    med_c = statistics.median(c_dec)
    med_dt = statistics.median(d_t)
    med_ct = statistics.median(c_t)
    rdec = mean_d / mean_c if mean_c else 0
    rtime = mean_dt / mean_ct if mean_ct else 0
    print(f"{n:>3}  {len(rs):>3}  {n_to:>3}  {n_sat:>3}   {n_uns:>3}    "
          f"{mean_d:>7.1f} / {med_d:>6.1f}    {mean_c:>7.1f} / {med_c:>6.1f}   "
          f"{mean_dt:>8.4f} / {med_dt:>7.4f}   {mean_ct:>9.6f} / {med_ct:>9.6f}   "
          f"{rdec:>6.1f}    {rtime:>8.1f}")

# Per-instance ratio detail
print("\nPer-instance decision ratios (DPLL decisions / CDCL decisions):")
for n in sorted(by_n):
    rs = by_n[n]
    ratios = [r['dpll_decisions'] / max(1, r['cdcl_decisions']) for r in rs]
    times_ratio = [r['dpll_time'] / max(1e-9, r['cdcl_time']) for r in rs]
    print(f"  n={n}: decisions-ratio = {[f'{x:.1f}' for x in ratios]}  time-ratio = {[f'{x:.0f}' for x in times_ratio]}")

# Outcomes: do they agree?
print("\nOutcome agreement check:")
disagree = 0
for r in rows:
    if r['dpll_status'] != r['cdcl_status'] and r['dpll_status'] != 'timeout':
        print(f"  DISAGREE: n={r['n']} seed={r['seed']} DPLL={r['dpll_status']} CDCL={r['cdcl_status']}")
        disagree += 1
print(f"  total disagreements (excluding DPLL timeouts): {disagree}")
