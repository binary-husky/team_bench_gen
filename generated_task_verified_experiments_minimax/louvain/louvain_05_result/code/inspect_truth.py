"""Inspect LFR ground truth (community memberships attached to nodes)."""

import networkx as nx
from collections import Counter

G = nx.LFR_benchmark_graph(
    n=1000,
    tau1=3.0,
    tau2=1.5,
    mu=0.4,
    average_degree=6,
    min_community=20,
    seed=0,
)

# nodes carry attribute 'community' = set of ground truth labels
truth = {}
for n, d in G.nodes(data=True):
    # LFR returns a set/frozenset of labels per node
    label = d.get("community")
    truth[n] = tuple(sorted(label)) if label is not None else None

n_true = len(set(truth.values()))
sizes = Counter(truth.values())
print(f"|V|={G.number_of_nodes()}, |E|={G.number_of_edges()}")
print(f"#ground truth communities = {n_true}")
print(f"min={min(sizes.values())}, max={max(sizes.values())}, "
      f"avg={sum(sizes.values())/n_true:.2f}")
print(f"distribution: {sorted(sizes.values())}")
