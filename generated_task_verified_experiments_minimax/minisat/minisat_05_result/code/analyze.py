"""
Analyze raw_results.csv:
  - per-(n,k) aggregates (mean / max conflicts and time across seeds)
  - per-graph "offset from chi" view: how conflict count scales as k approaches χ
  - produce matplotlib figures
"""
import csv
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

rows = []
with open('raw_results.csv') as f:
    r = csv.DictReader(f)
    for row in r:
        row['n'] = int(row['n']); row['k'] = int(row['k'])
        row['seed'] = int(row['seed'])
        row['time_s'] = float(row['time_s'])
        row['conflicts'] = int(row['conflicts'])
        row['sat'] = (row['sat'] == 'True')
        rows.append(row)

# chi per (n,seed)
chi = {(r['n'], r['seed']): None for r in rows}
for r in rows:
    if r['sat']:
        prev = chi[(r['n'], r['seed'])]
        if prev is None or r['k'] < prev:
            chi[(r['n'], r['seed'])] = r['k']

# add offset
for r in rows:
    r['chi'] = chi[(r['n'], r['seed'])]
    r['delta'] = r['k'] - r['chi']   # negative: UNSAT cases below chi
    r['is_sat'] = r['sat']

# ---------------- per (n, k) aggregates ----------------------------------
agg = defaultdict(list)  # (n, k) -> list of dicts
for r in rows:
    agg[(r['n'], r['k'])].append(r)

per_k_summary = []
for (n, k), lst in sorted(agg.items()):
    per_k_summary.append({
        'n': n, 'k': k,
        'n_graphs': len(lst),
        'sat_count': sum(1 for r in lst if r['sat']),
        'mean_conflicts': statistics.mean(r['conflicts'] for r in lst),
        'max_conflicts': max(r['conflicts'] for r in lst),
        'mean_time_s': statistics.mean(r['time_s'] for r in lst),
        'max_time_s': max(r['time_s'] for r in lst),
    })

with open('per_k_summary.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(per_k_summary[0].keys()))
    w.writeheader()
    w.writerows(per_k_summary)

# ---------------- per (n, delta) aggregates -------------------------------
agg_d = defaultdict(list)
for r in rows:
    agg_d[(r['n'], r['delta'])].append(r)

per_delta = []
for (n, d), lst in sorted(agg_d.items()):
    per_delta.append({
        'n': n, 'delta': d,
        'n_graphs': len(lst),
        'sat_count': sum(1 for r in lst if r['sat']),
        'mean_conflicts': statistics.mean(r['conflicts'] for r in lst),
        'mean_time_s': statistics.mean(r['time_s'] for r in lst),
    })

with open('per_delta_summary.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(per_delta[0].keys()))
    w.writeheader()
    w.writerows(per_delta)

# ---------------- distribution of chi per n -------------------------------
chi_dist = defaultdict(list)
for (n, s), c in chi.items():
    chi_dist[n].append(c)
for n in sorted(chi_dist):
    print(f"n={n}: chi values = {sorted(chi_dist[n])}, "
          f"mean={statistics.mean(chi_dist[n]):.2f}, "
          f"min={min(chi_dist[n])}, max={max(chi_dist[n])}")

# ---------------- plots ---------------------------------------------------
ns = [10, 15, 20]
colors = {10: 'tab:blue', 15: 'tab:orange', 20: 'tab:green'}

# Plot 1: conflicts vs k (per n)
fig, ax = plt.subplots(figsize=(7, 4.5))
for n in ns:
    xs, ys = [], []
    for s in per_k_summary:
        if s['n'] == n:
            xs.append(s['k']); ys.append(s['mean_conflicts'])
    ax.plot(xs, ys, '-o', color=colors[n], label=f'n={n}')
ax.set_xlabel('k  (number of colors probed)')
ax.set_ylabel('mean conflicts (over 8 seeds)')
ax.set_title('CDCL conflicts vs k  (random G(n, 0.5))')
ax.set_yscale('log')
ax.grid(True, which='both', linestyle=':')
ax.legend()
fig.tight_layout()
fig.savefig('conflicts_vs_k.png', dpi=130)
plt.close(fig)

# Plot 2: time vs k
fig, ax = plt.subplots(figsize=(7, 4.5))
for n in ns:
    xs, ys = [], []
    for s in per_k_summary:
        if s['n'] == n:
            xs.append(s['k']); ys.append(s['mean_time_s'] * 1000.0)   # ms
    ax.plot(xs, ys, '-o', color=colors[n], label=f'n={n}')
ax.set_xlabel('k  (number of colors probed)')
ax.set_ylabel('mean solve time  [ms]')
ax.set_title('Solve time vs k  (random G(n, 0.5))')
ax.set_yscale('log')
ax.grid(True, which='both', linestyle=':')
ax.legend()
fig.tight_layout()
fig.savefig('time_vs_k.png', dpi=130)
plt.close(fig)

# Plot 3: max conflicts vs k  (worst case among seeds)
fig, ax = plt.subplots(figsize=(7, 4.5))
for n in ns:
    xs, ys = [], []
    for s in per_k_summary:
        if s['n'] == n:
            xs.append(s['k']); ys.append(s['max_conflicts'])
    ax.plot(xs, ys, '-o', color=colors[n], label=f'n={n}')
ax.set_xlabel('k')
ax.set_ylabel('max conflicts (over 8 seeds)')
ax.set_title('Worst-case CDCL conflicts vs k')
ax.set_yscale('log')
ax.grid(True, which='both', linestyle=':')
ax.legend()
fig.tight_layout()
fig.savefig('max_conflicts_vs_k.png', dpi=130)
plt.close(fig)

# Plot 4: conflicts vs n, per k offset
fig, ax = plt.subplots(figsize=(7, 4.5))
for d in sorted(set(p['delta'] for p in per_delta)):
    xs, ys = [], []
    for p in per_delta:
        if p['delta'] == d:
            xs.append(p['n']); ys.append(p['mean_conflicts'])
    ax.plot(xs, ys, '-o', label=f'k − χ = {d:+d}')
ax.set_xlabel('n  (graph size)')
ax.set_ylabel('mean conflicts')
ax.set_title('Conflicts vs n, grouped by offset from chromatic number')
ax.set_yscale('log')
ax.grid(True, which='both', linestyle=':')
ax.legend()
fig.tight_layout()
fig.savefig('conflicts_vs_n.png', dpi=130)
plt.close(fig)

# Plot 5: time vs n, per k offset
fig, ax = plt.subplots(figsize=(7, 4.5))
for d in sorted(set(p['delta'] for p in per_delta)):
    xs, ys = [], []
    for p in per_delta:
        if p['delta'] == d:
            xs.append(p['n']); ys.append(p['mean_time_s'] * 1000.0)
    ax.plot(xs, ys, '-o', label=f'k − χ = {d:+d}')
ax.set_xlabel('n  (graph size)')
ax.set_ylabel('mean solve time  [ms]')
ax.set_title('Solve time vs n, grouped by offset from chromatic number')
ax.set_yscale('log')
ax.grid(True, which='both', linestyle=':')
ax.legend()
fig.tight_layout()
fig.savefig('time_vs_n.png', dpi=130)
plt.close(fig)

# Print a compact textual summary
print('\n=== per (n,k) summary ===')
print(f"{'n':>3} {'k':>2} {'graphs':>6} {'sat':>3} "
      f"{'mean_conf':>10} {'max_conf':>8} {'mean_ms':>10}")
for s in per_k_summary:
    print(f"{s['n']:>3} {s['k']:>2} {s['n_graphs']:>6} {s['sat_count']:>3} "
          f"{s['mean_conflicts']:>10.1f} {s['max_conflicts']:>8d} "
          f"{s['mean_time_s']*1000:>10.4f}")

print('\n=== per (n, k-chi) summary ===')
print(f"{'n':>3} {'delta':>5} {'graphs':>6} {'sat':>3} "
      f"{'mean_conf':>10} {'mean_ms':>10}")
for p in per_delta:
    print(f"{p['n']:>3} {p['delta']:>+5} {p['n_graphs']:>6} {p['sat_count']:>3} "
          f"{p['mean_conflicts']:>10.1f} {p['mean_time_s']*1000:>10.4f}")
