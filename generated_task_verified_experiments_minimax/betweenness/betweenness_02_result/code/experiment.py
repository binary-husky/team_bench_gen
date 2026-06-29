"""
Correctness verification of NetworkX Brandes betweenness centrality vs.
a naive pair-wise shortest-path enumeration baseline.

- Brandes: networkx.betweenness_centrality (default normalization = True).
- Naive:   for every unordered pair (s,t) with s != t, run BFS, enumerate
           all shortest paths in the BFS-layer DAG, and for each interior
           node v (v != s,t) add sigma_st(v)/sigma_st to its betweenness.
           Apply the same normalization factor as NetworkX.

For undirected graphs each unordered pair (s,t) is processed once (matching
NetworkX's convention).  Endpoints are excluded.
"""

from collections import deque

import networkx as nx


# --------------------------------------------------------------------------- #
# Naive implementation
# --------------------------------------------------------------------------- #

def _shortest_path_contributions(G, s, t):
    """
    BFS from s to t over G.  For every interior node v on a shortest s-t
    path return how many such paths go through v.  Also returns sigma_st,
    the total number of distinct shortest s-t paths.

    Implements the standard BFS-DAG bookkeeping used in Brandes (2001):
        parents[v] = predecessors of v on shortest paths from s
        sigma[v]   = number of shortest s-v paths
        delta[v]   = number of shortest s-v paths whose continuation from
                     v to t leads back to t (i.e. number of s-t shortest
                     paths that pass through v as an interior endpoint).
    """
    if s == t:
        return 0, {}

    parents = {s: []}
    dist = {s: 0}
    sigma = {s: 1}
    frontier = deque([s])

    while frontier:
        u = frontier.popleft()
        d_u = dist[u]
        for w in G.neighbors(u):
            if w not in dist:
                dist[w] = d_u + 1
                sigma[w] = 0
                parents[w] = []
                frontier.append(w)
            if dist[w] == d_u + 1:
                sigma[w] += sigma[u]
                if u not in parents[w]:
                    parents[w].append(u)

    if t not in dist:
        return 0, {}

    sigma_st = sigma[t]

    # Reverse-BFS pass: count shortest v -> t paths in the DAG.  (The
    # length of every such path equals dist[t] - dist[v], so we use that
    # directly below to filter nodes that actually lie on a shortest
    # s-t path.)
    delta = {v: 0 for v in dist}
    delta[t] = 1
    order = sorted(dist.keys(), key=lambda x: dist[x], reverse=True)
    for v in order:
        if v == s:
            continue
        for p in parents.get(v, []):
            delta[p] += delta[v]

    # Number of shortest s->t paths that pass through interior node v is
    #   sigma_st(v) = sigma_sv * sigma_vt
    # provided that v is actually on some shortest s-t path, i.e.
    #   dist[s][v] + dist[v][t] == dist[s][t].
    contributions = {}
    dist_t = dist[t]
    for v in delta:
        if v in (s, t):
            continue
        # Only count v when it sits on a shortest s-t path.
        if sigma[v] > 0 and delta[v] > 0 and dist[v] + (dist_t - dist[v]) == dist_t:
            contributions[v] = sigma[v] * delta[v]
    return sigma_st, contributions


def naive_betweenness_centrality(G, normalized=True):
    """
    Betweenness centrality via explicit enumeration of every node pair.
    For undirected graphs each unordered pair (s,t) is processed once
    (NetworkX convention).  Endpoints (v == s or v == t) are excluded.
    """
    n = G.number_of_nodes()
    if n < 3:
        return {v: 0.0 for v in G.nodes()}

    bc = {v: 0.0 for v in G.nodes()}
    nodes = list(G.nodes())

    if not G.is_directed():
        for i, s in enumerate(nodes):
            for t in nodes[i + 1:]:
                sigma_st, contribs = _shortest_path_contributions(G, s, t)
                if sigma_st == 0:
                    continue
                for v, c in contribs.items():
                    bc[v] += c / sigma_st
    else:
        for s in nodes:
            for t in nodes:
                if s == t:
                    continue
                sigma_st, contribs = _shortest_path_contributions(G, s, t)
                if sigma_st == 0:
                    continue
                for v, c in contribs.items():
                    bc[v] += c / sigma_st

    if normalized:
        if G.is_directed():
            scale = 1.0 / ((n - 1) * (n - 2))
        else:
            scale = 2.0 / ((n - 1) * (n - 2))
        for v in bc:
            bc[v] *= scale

    return bc


# --------------------------------------------------------------------------- #
# Experiment
# --------------------------------------------------------------------------- #

def make_graphs():
    graphs = []

    # 1. Zachary's karate club.
    graphs.append(("karate_club", nx.karate_club_graph()))

    # 2. Erdős–Rényi random graphs, several sizes and densities.
    er_specs = [
        (15, 0.20), (15, 0.40),
        (20, 0.15), (20, 0.30),
        (30, 0.10), (30, 0.20), (30, 0.35),
        (50, 0.05), (50, 0.10),
    ]
    for seed in (1, 2, 3):
        for n, p in er_specs:
            G = nx.erdos_renyi_graph(n, p, seed=seed)
            graphs.append((f"ER_n{n}_p{p}_s{seed}", G))

    # 3. Connected-ish random graphs from gn_graph (directed) -- convert
    #    to undirected.
    for seed in (1, 2, 3):
        for n, k in [(20, 3), (30, 4), (50, 5)]:
            G_d = nx.gn_graph(n, seed=seed)
            G = nx.Graph()
            G.add_nodes_from(G_d.nodes())
            G.add_edges_from((u, v) for u, v in G_d.edges() if u != v)
            graphs.append((f"GN_n{n}_k{k}_s{seed}", G))

    return graphs


def run():
    rows = []
    graphs = make_graphs()
    print(f"Total graphs: {len(graphs)}")

    for label, G in graphs:
        # Reduce to the largest connected component so every pair of
        # nodes has at least one path; both methods assume this.
        label_eff = label
        if not nx.is_connected(G):
            components = sorted(nx.connected_components(G), key=len, reverse=True)
            G = G.subgraph(components[0]).copy()
            label_eff = label + "_LCC"

        n = G.number_of_nodes()
        m = G.number_of_edges()

        brandes_bc = nx.betweenness_centrality(G, normalized=True)
        naive_bc = naive_betweenness_centrality(G, normalized=True)

        max_abs_diff = 0.0
        for v in G.nodes():
            d = abs(brandes_bc[v] - naive_bc[v])
            if d > max_abs_diff:
                max_abs_diff = d
        rows.append((label_eff, n, m, max_abs_diff))
        print(f"  {label_eff:30s}  n={n:3d}  m={m:4d}  "
              f"max|ΔBC|={max_abs_diff:.3e}")

    return rows


if __name__ == "__main__":
    rows = run()

    out_path = "/data/workspace/admin/happy_lake/.verify_judge_minimax/betweenness/betweenness_02/results.txt"
    with open(out_path, "w") as fh:
        for label, n, m, d in rows:
            fh.write(f"{label}\t{n}\t{m}\t{d:.15e}\n")
    print(f"\nResults written to {out_path}")