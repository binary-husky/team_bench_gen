"""
Betweenness correctness check.

Goal (task.md): verify that NetworkX's Brandes-based betweenness_centrality
agrees *node-by-node* with a NAIVE baseline that, for every node pair (s,t),
uses BFS to enumerate ALL shortest paths s->t and accumulates
sigma_st(v)/sigma_st over interior nodes v.

Reference material: Ulrik Brandes, "A Faster Algorithm for Betweenness
Centrality" (brandes01centrality.pdf) -- defines BC(v) = sum_{s!=v!=t}
sigma_st(v)/sigma_st and the dependency-accumulation that achieves O(nm).

Conventions (so the two methods are directly comparable):
  * undirected graph -> each unordered pair {s,t} counted ONCE (the ordered
    accumulation from the per-source loop is divided by 2). This is exactly
    what NetworkX `normalized=False` does (its _rescale multiplies undirected
    raw values by 0.5).
  * endpoints excluded (interior nodes only) <-> NetworkX endpoints=False.
"""

import math
from collections import deque

import networkx as nx


# --------------------------------------------------------------------------
# NAIVE baseline: explicit pairwise shortest-path enumeration
# --------------------------------------------------------------------------
def bfs_from(G, s):
    """Single-source BFS returning (dist, sigma, pred).

    dist[v] : shortest-path distance from s to v (only present if reachable)
    sigma[v]: number of shortest paths from s to v
    pred[v] : list of predecessors of v on shortest paths from s
    """
    dist = {s: 0}
    sigma = {v: 0 for v in G.nodes()}
    sigma[s] = 1
    pred = {v: [] for v in G.nodes()}
    Q = deque([s])
    while Q:
        v = Q.popleft()
        for w in G.neighbors(v):
            if w not in dist:              # first time we see w
                dist[w] = dist[v] + 1
                Q.append(w)
            if dist[w] == dist[v] + 1:     # v is a predecessor of w on a SP
                pred[w].append(v)
                sigma[w] += sigma[v]
    return dist, sigma, pred


def enumerate_shortest_paths(s, t, pred):
    """Yield every shortest s->t path (as a node list) using the pred DAG."""
    if t == s:
        yield [s]
        return
    for p in pred[t]:
        for prefix in enumerate_shortest_paths(s, p, pred):
            yield prefix + [t]


def naive_betweenness(G, path_cap=2_000_000):
    """Naive pairwise betweenness for an undirected graph.

    Returns a dict node->BC equal to  sum_{unordered {s,t}} sigma_st(v)/sigma_st
    (interior nodes only), i.e. NetworkX `normalized=False`.

    For robustness, if a pair has more than `path_cap` shortest paths, we fall
    back to the identity sigma_st(v) = sigma_sv * sigma_vt (valid when
    d(s,v)+d(v,t)=d(s,t)); for the small random graphs here the explicit
    enumeration is always used.
    """
    nodes = list(G.nodes())
    BC = {v: 0.0 for v in nodes}

    for s in nodes:
        dist, sigma, pred = bfs_from(G, s)
        for t in nodes:
            if t == s or t not in dist:
                continue
            sigma_st = sigma[t]
            if sigma_st == 0:
                continue
            if sigma_st <= path_cap:
                cnt = {}
                for path in enumerate_shortest_paths(s, t, pred):
                    for v in path[1:-1]:       # interior nodes only
                        cnt[v] = cnt.get(v, 0) + 1
                for v, c in cnt.items():
                    BC[v] += c / sigma_st
            else:
                dt, sigt, _ = bfs_from(G, t)
                dst = dist[t]
                for v in nodes:
                    if v == s or v == t:
                        continue
                    if v in dist and v in dt and dist[v] + dt[v] == dst:
                        BC[v] += sigma[v] * sigt[v] / sigma_st

    # undirected dedup: each unordered pair was accumulated from both (s,t),(t,s)
    for v in nodes:
        BC[v] *= 0.5
    return BC


# --------------------------------------------------------------------------
# Graph suite
# --------------------------------------------------------------------------
def connected_gnp(n, p, seed):
    """A *connected* random graph: draw G(n,p); if disconnected, stitch the
    components together with a few edges."""
    G = nx.gnp_random_graph(n, p, seed=seed)
    if not nx.is_connected(G):
        comps = list(nx.connected_components(G))
        for i in range(len(comps) - 1):
            a = next(iter(comps[i]))
            b = next(iter(comps[i + 1]))
            G.add_edge(a, b)
    return G


def build_suite():
    suite = []
    # 1. Zachary karate club (fixed real graph)
    suite.append(("karate_club", nx.karate_club_graph()))

    # 2-4. ER n=15, p=0.2, three seeds
    for seed in (0, 1, 2):
        suite.append((f"ER_n15_p0.20_s{seed}",
                      nx.gnp_random_graph(15, 0.20, seed=seed)))
    # 5-7. ER n=20, p=0.3, three seeds (denser)
    for seed in (0, 1, 2):
        suite.append((f"ER_n20_p0.30_s{seed}",
                      nx.gnp_random_graph(20, 0.30, seed=seed)))
    # 8-9. ER n=30, p=0.15, two seeds
    for seed in (0, 1):
        suite.append((f"ER_n30_p0.15_s{seed}",
                      nx.gnp_random_graph(30, 0.15, seed=seed)))
    # 10. ER n=50, p=0.08 (sparse-ish)
    suite.append(("ER_n50_p0.08_s0", nx.gnp_random_graph(50, 0.08, seed=0)))

    # 11. Connected random graph n=20
    suite.append(("CONN_n20_p0.25_s3", connected_gnp(20, 0.25, seed=3)))
    # 12. Connected random graph n=50
    suite.append(("CONN_n50_p0.10_s5", connected_gnp(50, 0.10, seed=5)))
    return suite


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------
def main():
    suite = build_suite()
    print(f"{'graph':<22}{'n':>4}{'m':>5}{'conn':>5}  "
          f"{'max|Δ| raw':>12}{'max|Δ| norm':>13}{'argmax_v':>9}")
    print("-" * 75)

    rows = []
    worst = 0.0
    for name, G in suite:
        n = G.number_of_nodes()
        m = G.number_of_edges()
        conn = "yes" if nx.is_connected(G) else "no"

        bc_brandes = nx.betweenness_centrality(G, normalized=False, weight=None)
        bc_brandes_n = nx.betweenness_centrality(G, normalized=True, weight=None)

        bc_naive = naive_betweenness(G)

        # normalized naive = unordered_sum / C(n-1,2)
        denom = math.comb(n - 1, 2) if n > 2 else 1
        bc_naive_n = {v: bc_naive[v] / denom for v in G.nodes()}

        d_raw = max(abs(bc_brandes[v] - bc_naive[v]) for v in G.nodes())
        d_norm = max(abs(bc_brandes_n[v] - bc_naive_n[v]) for v in G.nodes())
        argmax_v = max(G.nodes(), key=lambda v: abs(bc_brandes[v] - bc_naive[v]))
        worst = max(worst, d_raw)

        rows.append({
            "name": name, "n": n, "m": m, "conn": conn,
            "d_raw": d_raw, "d_norm": d_norm, "argmax_v": argmax_v,
        })
        print(f"{name:<22}{n:>4}{m:>5}{conn:>5}  "
              f"{d_raw:>12.3e}{d_norm:>13.3e}{argmax_v:>9}")

    print("-" * 75)
    print(f"Worst max|Δ| (raw) across all graphs: {worst:.3e}")
    return rows


if __name__ == "__main__":
    main()
