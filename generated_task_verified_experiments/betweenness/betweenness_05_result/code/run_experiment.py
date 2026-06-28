#!/usr/bin/env python3
"""
Betweenness centrality distribution across graph topologies.

Reference material: U. Brandes, "A Faster Algorithm for Betweenness Centrality",
J. Mathematical Sociology 25(2):163-177, 2001 (Brandes' O(nm) algorithm,
which is exactly what NetworkX's nx.betweenness_centrality implements).

Goal: show that the *shape* of the betweenness-centrality distribution is
highly sensitive to graph structure, by comparing 5 canonical topologies
at comparable node counts (n ~= 100).
"""
import json
import math
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED = 7
N = 100  # target node count for every topology

# ----------------------------------------------------------------------
# 1. Build the 5 topologies
# ----------------------------------------------------------------------
graphs = {}

# Path P_n : n nodes in a line
graphs["Path P_100"] = nx.path_graph(N)

# Cycle C_n : n nodes in a ring
graphs["Cycle C_100"] = nx.cycle_graph(N)

# Star S_n : 1 center + (n-1) leaves   (star_graph(k) has k+1 nodes)
graphs["Star S_100"] = nx.star_graph(N - 1)

# 2-D grid  10 x 10 = 100 nodes
graphs["Grid 10x10"] = nx.grid_2d_graph(10, 10)

# Random partition graph (community structure): 4 communities of 25 nodes,
# dense intra-community edges, sparse inter-community edges.  p_out=0.01 keeps
# the graph connected while leaving a clean split between "bridge" nodes
# (spanning communities) and purely local nodes.
sizes = [25, 25, 25, 25]
G_part = nx.random_partition_graph(sizes, p_in=0.5, p_out=0.01, seed=SEED)
graphs["Partition (4x25)"] = G_part


# ----------------------------------------------------------------------
# 2. Helpers
# ----------------------------------------------------------------------
def gini(values):
    """Gini coefficient of a list of non-negative numbers.

    G = (sum_i sum_j |x_i - x_j|) / (2 n sum x_i)
      = (2 sum_i i*x_i) / (n sum x_i) - (n+1)/n   (x sorted ascending)
    Returns float('nan') if total == 0.
    """
    x = np.asarray(values, dtype=float)
    n = len(x)
    total = x.sum()
    if total == 0:
        return float("nan")
    xs = np.sort(x)
    idx = np.arange(1, n + 1)
    return (2.0 * np.sum(idx * xs)) / (n * total) - (n + 1) / n


def describe_node(g, node):
    """Human-friendly label for a node id (grids use (i,j) tuples)."""
    if isinstance(node, tuple):
        deg = g.degree(node)
        # grid centre: middle row/col
        return f"{node} (degree {deg})"
    return str(node)


def grid_position_label(node, m=10, nn=10):
    """Classify a grid node by its position (corner / edge / interior / centre)."""
    i, j = node
    on_border = (i == 0 or i == m - 1 or j == 0 or j == nn - 1)
    dist_to_center = max(abs(i - (m - 1) / 2), abs(j - (nn - 1) / 2))
    return on_border, dist_to_center


# ----------------------------------------------------------------------
# 3. Compute betweenness for every topology
# ----------------------------------------------------------------------
results = {}
all_bc = {}

for name, g in graphs.items():
    bc = nx.betweenness_centrality(g, normalized=False)  # raw (unordered-pair) counts
    nodes = list(g.nodes())
    vals = np.array([bc[n] for n in nodes], dtype=float)

    # node(s) attaining the max
    maxv = vals.max()
    argmax_nodes = [n for n in nodes if bc[n] == maxv]

    g = g  # noqa
    # Build a readable "max-node position" label
    if name.startswith("Path"):
        idxs = [n for n in argmax_nodes]
        pos = f"middle node(s) {sorted(idxs)} of {N}"
    elif name.startswith("Cycle"):
        pos = "all nodes tie (symmetric ring)"
    elif name.startswith("Star"):
        pos = f"central hub node 0 (degree {graphs[name].degree(0)})"
    elif name.startswith("Grid"):
        labels = []
        for n in argmax_nodes:
            on_border, dc = grid_position_label(n)
            labels.append(f"{n} (dist-to-centre {dc:.1f})")
        pos = "central region: " + ", ".join(sorted(set(labels)))
    else:  # partition / community
        # figure out community of each max node + whether it has inter-community edges
        labels = []
        cum = 0
        comm_bounds = []
        for s in sizes:
            comm_bounds.append((cum, cum + s))
            cum += s
        for n in argmax_nodes:
            comm = next(k for k, (a, b) in enumerate(comm_bounds) if a <= n < b)
            inter = sum(1 for nb in graphs[name].neighbors(n)
                        if not (comm_bounds[comm][0] <= nb < comm_bounds[comm][1]))
            labels.append(f"node {n} (comm {comm}, {inter} inter-comm. edges)")
        pos = "; ".join(sorted(set(labels)))

    results[name] = {
        "n_nodes": g.number_of_nodes(),
        "n_edges": g.number_of_edges(),
        "max_bc": float(maxv),
        "max_bc_nodes": pos,
        "gini": float(gini(vals)),
        "mean_bc": float(vals.mean()),
        "min_bc": float(vals.min()),
        "frac_zero": float((vals == 0).mean()),
    }

    # community graph: bridge vs internal contrast
    if name.startswith("Partition"):
        Gp = graphs[name]
        cum = 0
        cb = []
        for s in sizes:
            cb.append((cum, cum + s))
            cum += 1 * s  # offset by community size
        def comm(u):
            return next(k for k, (a, b) in enumerate(cb) if a <= u < b)
        def inter_edges(u):
            return sum(1 for nb in Gp.neighbors(u) if comm(nb) != comm(u))
        bridge_bc = [bc[u] for u in Gp.nodes() if inter_edges(u) > 0]
        intern_bc = [bc[u] for u in Gp.nodes() if inter_edges(u) == 0]
        results[name]["n_bridge"] = len(bridge_bc)
        results[name]["n_internal"] = len(intern_bc)
        results[name]["mean_bc_bridge"] = float(np.mean(bridge_bc))
        results[name]["mean_bc_internal"] = float(np.mean(intern_bc)) if intern_bc else 0.0
        # correlation between #inter-community edges and BC
        ied = np.array([inter_edges(u) for u in Gp.nodes()])
        bcv = np.array([bc[u] for u in Gp.nodes()])
        if ied.std() > 0 and bcv.std() > 0:
            results[name]["corr_interdeg_bc"] = float(np.corrcoef(ied, bcv)[0, 1])
        results[name]["max_node_inter_edges"] = int(inter_edges(argmax_nodes[0]))

    all_bc[name] = vals

# ----------------------------------------------------------------------
# 4. Histograms
# ----------------------------------------------------------------------
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
axes = axes.ravel()
for k, (name, vals) in enumerate(all_bc.items()):
    ax = axes[k]
    # use enough bins; exclude nothing
    nz = vals[vals > 0]
    if nz.size and vals.min() != vals.max():
        ax.hist(vals, bins=20, color="#4C72B0", edgecolor="white")
    else:
        # degenerate (e.g. cycle = all equal, star = bimodal 0 vs hub)
        ax.hist(vals, bins=np.unique(vals).size or 1, color="#4C72B0", edgecolor="white")
    ax.set_title(f"{name}\nmax BC={results[name]['max_bc']:.1f}, "
                 f"Gini={results[name]['gini']:.3f}", fontsize=10)
    ax.set_xlabel("betweenness centrality")
    ax.set_ylabel("# nodes")
axes[5].axis("off")  # 5 plots, 6th panel empty
fig.suptitle("Betweenness centrality distributions across topologies (n≈100, normalized=False)",
             fontsize=12)
fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig("hist_betweenness_05.png", dpi=110)
print("saved hist_betweenness_05.png")

# ----------------------------------------------------------------------
# 5. Print + dump JSON
# ----------------------------------------------------------------------
print("\n=== RESULTS ===")
print(f"{'topology':<20}{'n':>5}{'m':>6}{'maxBC':>12}{'Gini':>8}{'%zero':>8}")
for name, r in results.items():
    print(f"{name:<20}{r['n_nodes']:>5}{r['n_edges']:>6}{r['max_bc']:>12.1f}"
          f"{r['gini']:>8.3f}{r['frac_zero']*100:>7.1f}%")
    print(f"   max-node: {r['max_bc_nodes']}")

with open("results_betweenness_05.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nsaved results_betweenness_05.json")
