"""Print size distributions for each γ partition."""

import json
import random
from collections import Counter

import community as community_louvain
import networkx as nx

G = nx.LFR_benchmark_graph(
    n=1000, tau1=3.0, tau2=1.5, mu=0.4,
    average_degree=6, min_community=20, seed=0,
)

random.seed(0)
for gamma in [0.5, 1.0, 1.5, 2.0]:
    p = community_louvain.best_partition(G, random_state=0, resolution=gamma)
    sizes = sorted(Counter(p.values()).values(), reverse=True)
    n = len(sizes)
    avg = sum(sizes) / n
    print(f"\nγ={gamma:.2f}: #C={n}, avg={avg:.2f}, max={max(sizes)}, min={min(sizes)}")
    # top 10 sizes
    print(f"  top-10 sizes: {sizes[:10]}")
    # count singletons
    sing = sum(1 for s in sizes if s == 1)
    print(f"  singletons: {sing}")
