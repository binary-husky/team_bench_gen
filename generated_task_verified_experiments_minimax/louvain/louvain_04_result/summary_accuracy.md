# Louvain accuracy on LFR benchmark graphs

We measure how well Louvain-detected communities agree with the
ground-truth LFR communities as the mixing parameter μ increases.

## Setup

- Graph generator: `networkx.LFR_benchmark_graph`
- Fixed parameters: `n=1000, tau1=3, tau2=1.5, average_degree=6, min_community=20, seed=0`
- Detection: `community.best_partition(G, random_state=0)`
- Agreement: `sklearn.metrics.normalized_mutual_info_score` (NMI),
  `sklearn.metrics.adjusted_rand_score` (ARI)
- Modularity: `community.modularity(partition, G)`
- Sole independent variable: μ

## Results

| μ | NMI | ARI | Q (modularity) | #detected communities | #true communities | #nodes | #edges |
|---|-----|-----|----------------|------------------------|--------------------|--------|--------|
| 0.1 | 0.9780 | 0.9385 | 0.9035 | 36 | 34 | 1000 | 2030 |
| 0.3 | 0.4147 | 0.1806 | 0.6033 | 21 | 34 | 1000 | 2073 |
| 0.5 | 0.2443 | 0.0457 | 0.5400 | 22 | 34 | 1000 | 2055 |
| 0.7 | 0.1667 | 0.0155 | 0.5163 | 21 | 34 | 1000 | 2088 |

## Discussion

As μ increases from 0.1 to 0.7, NMI decreases monotonically (0.978 → 0.167), ARI decreases monotonically (0.938 → 0.015), and modularity Q decreases monotonically (0.903 → 0.516).

Higher μ means a larger fraction of each node's edges leave its own
community, i.e. the planted community structure becomes weaker. With
weak structure (μ=0.7) Louvain has trouble recovering the planted
partition — both NMI and ARI drop sharply, and the number of detected
communities diverges from the ground truth. With strong structure
(μ=0.1) Louvain recovers the ground truth almost perfectly. Modularity
remains relatively high even at μ=0.7 because the detected partition
still has dense internal connections, but those detected communities
no longer match the true ones — illustrating the well-known
resolution / degeneracy issue with modularity-maximising methods when
structure is weak.
