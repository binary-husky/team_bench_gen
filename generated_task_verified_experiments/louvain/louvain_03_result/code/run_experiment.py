import networkx as nx
import community as community
import numpy as np
import time

# Fixed LFR parameters
TAU1 = 3
TAU2 = 1.5
MU = 0.4
AVG_DEG = 6
MIN_COMM = 20
SEED = 0

NS = [500, 1000, 2000, 4000]


def gini(values):
    """Gini coefficient of a list of (community) sizes."""
    vals = np.array(sorted(values), dtype=float)
    n = len(vals)
    if n == 0 or vals.sum() == 0:
        return float('nan')
    # mean absolute difference / (2 * mean)
    cumsum = np.cumsum(vals)
    # G = (2*sum(i*x_i) - (n+1)*sum(x)) / (n*sum(x))  (sorted ascending)
    index = np.arange(1, n + 1)
    return (2 * np.sum(index * vals) - (n + 1) * np.sum(vals)) / (n * np.sum(vals))


def run(n):
    t0 = time.time()
    G = nx.LFR_benchmark_graph(
        n, TAU1, TAU2, MU, average_degree=AVG_DEG,
        min_community=MIN_COMM, seed=SEED)
    # LFR returns nodes with 'community' attribute (a set)
    # build graph without multi-edges
    G = nx.Graph(G)
    print(f"  n={n}: nodes={G.number_of_nodes()} edges={G.number_of_edges()} "
          f"gen_time={time.time()-t0:.1f}s", flush=True)

    t1 = time.time()
    partition = community.best_partition(G, random_state=SEED)
    Q = community.modularity(partition, G)

    # community sizes
    comm = {}
    for node, c in partition.items():
        comm.setdefault(c, []).append(node)
    sizes = sorted((len(v) for v in comm.values()), reverse=True)
    k = len(sizes)
    g = gini(sizes)

    # ground-truth community info
    gt_comm = {}
    for node, d in G.nodes(data=True):
        # community attribute is a frozenset/set of node ids
        c = tuple(sorted(d['community']))
        gt_comm.setdefault(c, []).append(node)
    gt_sizes = sorted((len(v) for v in gt_comm.values()), reverse=True)
    gt_k = len(gt_sizes)
    gt_g = gini(gt_sizes)

    print(f"  detected: k={k} Q={Q:.4f} gini={g:.4f} "
          f"size_range=({sizes[-1]},{sizes[0]})  "
          f"GT: k={gt_k} gini={gt_g:.4f}  louvain_time={time.time()-t1:.1f}s",
          flush=True)
    return dict(n=n, nodes=G.number_of_nodes(), edges=G.number_of_edges(),
                k=k, Q=Q, sizes=sizes, gini=g,
                gt_k=gt_k, gt_sizes=gt_sizes, gt_gini=gt_g)


if __name__ == '__main__':
    results = []
    for n in NS:
        r = run(n)
        results.append(r)
    # save
    import json
    out = {r['n']: {kk: (vv if not isinstance(vv, list) else vv) for kk, vv in r.items()} for r in results}
    with open('results.json', 'w') as f:
        json.dump(out, f, indent=2)
    print("DONE", flush=True)
