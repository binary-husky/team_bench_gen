# Community count, modularity and size distribution as the graph grows
## Louvain on LFR benchmark graphs (hierarchical unfolding across scales)

### Setup
- **Graph family**: LFR benchmark (`networkx.generators.community.LFR_benchmark_graph`).
- **Fixed parameters** (all `n`): `tau1=3`, `tau2=1.5`, `mu=0.4`, `average_degree=6`,
  `min_community=20`, `seed=0`.
- **Variable**: `n ∈ {500, 1000, 2000, 4000}` (doubling).
- **Algorithm**: `community.community_louvain.best_partition(G, random_state=0)`.
- **Metrics**: number of communities `k`, modularity `Q`, descending community
  size list, Gini coefficient of the size list
  (`G = (2·Σ i·x_{(i)}) / (k·Σx) − (k+1)/k`).
- **Ground-truth community attribute leaked by the LFR generator was removed
  from each node before running Louvain**, so the algorithm only sees topology.

### Results

| `n` | nodes | edges | `k` | `Q` | max size | min size | median size | mean size | Gini (all) | Gini (≥2) | singletons |
|----:|------:|------:|----:|----:|---------:|---------:|------------:|----------:|-----------:|----------:|-----------:|
|  500 |  500 |  1187 | 15 | 0.4508 | 65 | 1 | 32 | 33.3 | 0.2331 | 0.1808 | 1 |
| 1000 | 1000 |  2044 | 20 | 0.5597 | 95 | 1 | 47 | 50.0 | 0.2570 | 0.2192 | 1 |
| 2000 | 2000 |  4511 | 22 | 0.5137 | 200 | 1 | 80 | 90.9 | 0.3537 | 0.2905 | 2 |
| 4000 | 4000 |  8768 | 35 | 0.5318 | 318 | 1 | 115 | 114.3 | 0.3795 | 0.2779 | 5 |

Louvain wall-time (CPU, single thread) per `n`:
0.04 s / 0.16 s / 0.42 s / 1.74 s — linear in `n·k` as expected.

### Full descending size distributions

- **`n = 500`** (15 communities):  
  `[65, 50, 46, 42, 39, 35, 34, 32, 31, 31, 29, 27, 23, 15, 1]`  
  Top-5 communities hold **48.4 %** of all nodes; 1 singleton.

- **`n = 1000`** (20 communities):  
  `[95, 95, 85, 66, 63, 63, 61, 53, 48, 47, 44, 43, 42, 42, 40, 35, 35, 27, 15, 1]`  
  Top-5 communities hold **40.4 %** of all nodes; 1 singleton.

- **`n = 2000`** (22 communities):  
  `[200, 180, 172, 171, 146, 134, 119, 113, 107, 85, 80, 79, 77, 64, 62, 59, 56, 34, 32, 28, 1, 1]`  
  Top-5 communities hold **43.5 %** of all nodes; 2 singletons.

- **`n = 4000`** (35 communities):  
  `[318, 312, 271, 214, 189, 182, 175, 162, 161, 139, 133, 133, 129, 128, 127, 120, 118, 115, 87, 85, 84, 82, 80, 80, 68, 67, 63, 61, 59, 53, 1, 1, 1, 1, 1]`  
  Top-5 communities hold **32.6 %** of all nodes; 5 singletons.

### How each metric varies with `n`

#### 1. Number of communities `k`
`k` grows but very slowly:

```
k : 15 → 20 → 22 → 35   as   n : 500 → 1000 → 2000 → 4000
```

A log-log fit `log k = 0.328 + 0.380 · log n` gives `k ∝ n^0.38`. Doubling `n`
adds roughly +2 communities at small `n` and +5–10 communities at the upper
end. Even though the LFR generator was told `min_community=20`, Louvain
detects far fewer (≈ n/33 for large `n`) because at `mu=0.4` it merges
ill-separated ground-truth groups, and the resolution limit of modularity
(known to forbid detecting communities smaller than `√m` in scale, per
Fortunato & Barthélemy) prevents Louvain from splitting the largest clusters.

#### 2. Modularity `Q`
`Q` jumps from **0.45** at `n=500` to a plateau in the **0.51–0.56** range for
`n ≥ 1000`. The trend is non-monotonic (Q at `n=2000` is slightly lower than at
`n=1000`), but the small-n value is genuinely lower. Interpretation: when the
graph is small enough that some "communities" are sampled with very few
internal edges, modularity is depressed; once the graph is large, the
signal-to-noise ratio stabilises and Louvain converges to a roughly constant
`Q ≈ 0.53`. These values are well below the `Q ≈ 0.8+` typical for crisp
synthetic benchmarks, reflecting `mu=0.4` (40 % of edges cross communities).

#### 3. Size distribution
Three structural facts are visible from the descending lists:

- **The distribution is heavy-tailed.** A handful of communities hold a large
  fraction of all nodes (32 %–48 % in the top-5 alone). On the rank-size plot
  the curves are nearly flat for the top ranks and only fall off sharply at the
  tail — a power-law-like regime rather than a uniform partition.
- **Maximum community size grows sub-linearly with `n`.** Max sizes are
  `65, 95, 200, 318`, fitting `max ∝ n^0.80`. So the biggest community does
  not eat a constant fraction of nodes; its share drops from 13 % at `n=500`
  to 8 % at `n=4000`, indicating that as more nodes are added Louvain is able
  to keep up by spawning new large clusters instead of just growing the same
  one.
- **Singletons appear in every graph and grow in number with `n`**
  (1, 1, 2, 5). They are 7 %–14 % of all detected communities and are an
  artefact of `mu=0.4`: peripheral nodes that Louvain cannot profitably merge
  anywhere remain as their own one-node community. The rank-size plots show
  them as the cliff at size 1.

#### 4. Gini coefficient of community sizes
The Gini **monotonically grows with `n`**:

```
Gini : 0.2331 (n=500) → 0.2570 (n=1000) → 0.3537 (n=2000) → 0.3795 (n=4000)
```

That is a 63 % increase from the smallest to the largest graph. Two
contributions:

- **Among "real" (≥2 nodes) communities, the Gini still rises** from
  0.18 → 0.22 → 0.29 → 0.28, i.e. inequality grows even when singletons are
  excluded. The size distribution becomes genuinely more uneven as `n` grows.
- **The fraction of singleton communities grows** from 6.7 % to 14.3 %, which
  further pushes the unconditional Gini up.

Both effects are consistent with the resolution-limit story: with finite
mixing (`mu=0.4`) and more nodes, the modularity landscape gains more local
optima, so Louvain keeps some communities small while letting a few
communities absorb disproportionately more nodes.

### Summary table of trends

| metric                  | trend with `n`           | approximate scaling |
|-------------------------|--------------------------|---------------------|
| `k` (community count)   | ↑ slowly                 | `k ∝ n^0.38`        |
| `Q` (modularity)        | ↑ then plateau at ≈0.53  | non-monotonic, ≈0.51–0.56 for `n ≥ 1000` |
| max community size      | ↑ sub-linearly           | `max ∝ n^0.80`      |
| mean community size     | ↑ sub-linearly           | `mean ≈ n/33` for large `n` |
| # singletons            | ↑                        | 1, 1, 2, 5          |
| top-5 mass fraction     | ↓ from ~48 % to ~33 %    | spreads out         |
| **Gini** (all)          | **↑ strongly**           | **0.23 → 0.38**     |
| **Gini** (≥2 nodes)     | **↑**                    | **0.18 → 0.28**     |

### Files produced
- `run_experiment.py` — generates LFR graphs, runs Louvain, computes metrics.
- `results.json` — per-`n` metrics.
- `community_sizes.json` — full descending size lists per `n`.
- `metrics_vs_n.png` — k, Q, Gini vs `n`.
- `rank_size.png` — rank-size plots (log-log) for all `n`.
- `summary_size_dist.md` — this report.

### Key takeaways
1. As the LFR graph grows from 500 to 4000 nodes (with `mu=0.4`),
   **the number of detected communities grows sub-linearly** (`k ∝ n^0.38`),
   far slower than `min_community=20` would suggest, because modularity's
   resolution limit and the high mixing rate merge many true ground-truth
   groups together.
2. **Modularity plateaus around Q ≈ 0.53** once `n` is large enough — well
   below the values typically reported for clean synthetic benchmarks,
   reflecting `mu=0.4`.
3. **Community sizes become more unequal** as `n` grows: Gini rises from
   0.23 to 0.38 (and 0.18 → 0.28 even after excluding singletons), while
   the share held by the top-5 communities drops from 48 % to 33 %. Louvain
   splits the new mass across several large clusters rather than one giant
   one, but the distribution it produces is increasingly heavy-tailed.
4. **Singletons are a persistent artefact** of Louvain at `mu=0.4`, growing
   in both count (1→5) and as a fraction of detected communities
   (6.7 % → 14.3 %), reflecting peripheral nodes that cannot be profitably
   merged.