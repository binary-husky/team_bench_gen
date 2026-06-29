"""
Experiment: Betweenness centrality distribution across graph topologies.

Goal: Compare betweenness centrality (BC) distribution morphology across
several canonical topologies with similar node counts. Verify that BC is
highly sensitive to graph structure.

Method: NetworkX exact betweenness_centrality (unnormalized).
Metrics: max BC, location of max-BC node(s), Gini coefficient.
"""

import os
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def gini(x):
    """Compute the Gini coefficient of a non-negative distribution.

    Reference: G = (sum_i sum_j |x_i - x_j|) / (2 n * sum_i x_i).
    Returns 0 when all values are equal; approaches 1 when one value holds
    nearly all of the total.
    """
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return 0.0
    if np.all(x == 0):
        return 0.0
    n = x.size
    # Use the sorted-differences form for numerical stability.
    x_sorted = np.sort(x)
    cum = np.cumsum(x_sorted)
    g = (n + 1 - 2 * np.sum(cum) / cum[-1]) / n
    return float(g)


def histogram_to_string(bc_values, bins=6):
    """Return a short text description of the BC histogram shape."""
    arr = np.asarray(bc_values, dtype=float)
    if arr.max() == 0:
        return "all zero"
    # Renormalize to fractions so the description is topology-agnostic.
    lo, hi = arr.min(), arr.max()
    edges = np.linspace(lo, hi, bins + 1)
    counts, _ = np.histogram(arr, bins=edges)
    parts = [f"[{edges[i]:.2f},{edges[i+1]:.2f}):{counts[i]}" for i in range(bins)]
    return " | ".join(parts)


def plot_histogram(bc_values, title, out_path):
    plt.figure(figsize=(5, 3.2))
    plt.hist(bc_values, bins=14, color="#3b6fb6", edgecolor="black", alpha=0.85)
    plt.title(title)
    plt.xlabel("betweenness centrality")
    plt.ylabel("count of nodes")
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close()


def report_topology(name, G, max_node_label=None):
    """Compute BC and produce a one-row summary for this graph."""
    bc = nx.betweenness_centrality(G, normalized=False)
    vals = np.array(list(bc.values()), dtype=float)
    max_bc = float(vals.max())
    max_nodes = [n for n, v in bc.items() if v == max_bc]
    if max_node_label is not None:
        max_nodes_str = ", ".join(str(max_node_label(n)) for n in max_nodes[:5])
    else:
        max_nodes_str = ", ".join(str(n) for n in max_nodes[:5])
    g = gini(vals)
    hist_str = histogram_to_string(vals)
    print(f"  topology     : {name}")
    print(f"  n / m        : {G.number_of_nodes()} / {G.number_of_edges()}")
    print(f"  max BC       : {max_bc:.4f}")
    print(f"  mean BC      : {vals.mean():.4f}")
    print(f"  std BC       : {vals.std():.4f}")
    print(f"  Gini         : {g:.4f}")
    print(f"  max-BC nodes : {max_nodes_str}")
    print(f"  histogram    : {hist_str}")
    print()
    return {
        "name": name,
        "n": G.number_of_nodes(),
        "m": G.number_of_edges(),
        "max_bc": max_bc,
        "mean_bc": float(vals.mean()),
        "std_bc": float(vals.std()),
        "gini": g,
        "max_bc_nodes": max_nodes,
        "hist_str": hist_str,
        "bc": bc,
    }


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # Use a target n around 100 so the random_partition_graph and grid are
    # easy to compare.  Use a fixed RNG seed so the experiment is reproducible.
    np.random.seed(0)
    N = 100

    rows = []

    # --- 1. Path graph P_n ---------------------------------------------------
    Pn = nx.path_graph(N)
    rows.append(report_topology(f"path P_{N}", Pn, max_node_label=int))

    # --- 2. Cycle graph C_n --------------------------------------------------
    Cn = nx.cycle_graph(N)
    rows.append(report_topology(f"cycle C_{N}", Cn, max_node_label=int))

    # --- 3. Star graph S_n ---------------------------------------------------
    Sn = nx.star_graph(N - 1)  # N nodes: 1 center + N-1 leaves
    rows.append(report_topology(
        f"star S_{N}", Sn,
        max_node_label=lambda n: "center" if n == 0 else f"leaf {n}",
    ))

    # --- 4. 2-D grid graph ----------------------------------------------------
    # Choose a roughly square grid close to N nodes: 10x10 = 100.
    side = int(round(np.sqrt(N)))
    grid = nx.grid_2d_graph(side, side)
    rows.append(report_topology(
        f"grid {side}x{side}", grid,
        max_node_label=lambda n: f"({n[0]},{n[1]})",
    ))

    # --- 5. Community graph (SBM via random_partition_graph) -----------------
    # Three communities of sizes 34, 33, 33 with denser internal edges and
    # sparser inter-community edges. This creates clear bridge nodes.
    sizes = [34, 33, 33]
    p_in = 0.30
    p_out = 0.01
    com = nx.random_partition_graph(sizes, p_in, p_out, seed=0)
    rows.append(report_topology(
        f"community graph ({len(sizes)} communities, sizes {sizes})",
        com,
        max_node_label=lambda n: f"v{n}",
    ))

    # --- Histograms ----------------------------------------------------------
    for r in rows:
        safe = r["name"].replace(" ", "_").replace("/", "_")
        path = os.path.join(out_dir, f"hist_{safe}.png")
        plot_histogram(list(r["bc"].values()), r["name"], path)
        r["hist_png"] = os.path.basename(path)

    # --- Tabular summary -----------------------------------------------------
    print("\n=== Summary table ===")
    print(f"{'topology':35s}  {'n':>4s}  {'max BC':>10s}  {'mean BC':>10s}  "
          f"{'std BC':>10s}  {'Gini':>6s}  max-BC node")
    for r in rows:
        mb = ", ".join(str(x) for x in r["max_bc_nodes"][:3])
        print(f"{r['name']:35s}  {r['n']:>4d}  {r['max_bc']:>10.3f}  "
              f"{r['mean_bc']:>10.3f}  {r['std_bc']:>10.3f}  "
              f"{r['gini']:>6.3f}  {mb}")

    # Save rows to a pickle so the writer script can pick them up.
    import json
    serialisable = []
    for r in rows:
        serialisable.append({
            "name": r["name"],
            "n": r["n"],
            "m": r["m"],
            "max_bc": r["max_bc"],
            "mean_bc": r["mean_bc"],
            "std_bc": r["std_bc"],
            "gini": r["gini"],
            "max_bc_nodes": [str(x) for x in r["max_bc_nodes"]],
            "hist_str": r["hist_str"],
            "hist_png": r["hist_png"],
        })
    with open(os.path.join(out_dir, "results.json"), "w") as fh:
        json.dump(serialisable, fh, indent=2)


if __name__ == "__main__":
    main()