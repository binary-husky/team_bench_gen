import networkx as nx
from networkx.generators.community import LFR_benchmark_graph
import community as community_louvain

# --- Generate LFR benchmark graph per task spec ---
params = dict(
    n=1000,
    tau1=3,
    tau2=1.5,
    mu=0.4,
    average_degree=6,
    min_community=20,
    seed=0,
)

G = None
attempts = []
for avg_deg in [6, 8, 10, 12]:
    for min_com in [20, 30, 40]:
        try:
            p = dict(params)
            p["average_degree"] = avg_deg
            p["min_community"] = min_com
            G = LFR_benchmark_graph(**p)
            attempts.append(f"SUCCESS avg_deg={avg_deg} min_community={min_com} n_nodes={G.number_of_nodes()} n_edges={G.number_of_edges()}")
            break
        except Exception as e:
            attempts.append(f"FAIL avg_deg={avg_deg} min_community={min_com}: {e}")
    if G is not None:
        break

print("=== Generation attempts ===")
for a in attempts:
    print(a)

if G is None:
    raise SystemExit("Could not generate LFR graph with any parameter set")

# Convert LFR node labels (which are ints) — community_louvain needs hashable nodes, ints fine
# LFR gives nodes as ints 0..n-1
print("\n=== Graph stats ===")
print("nodes:", G.number_of_nodes(), "edges:", G.number_of_edges())

# --- generate_dendrogram with fixed random_state ---
dendro = community_louvain.generate_dendrogram(G, random_state=0)
print("\n=== Dendrogram ===")
print("total passes (levels):", len(dendro))
print("graph induced at each level - node counts:", [len(lvl) for lvl in dendro])

# --- For each level, map partition back to original nodes, compute Q and #communities ---
results = []
print("\n=== Per-pass convergence ===")
print(f"{'level':>5} {'Q':>12} {'#communities':>14}")
for level in range(len(dendro)):
    partition = community_louvain.partition_at_level(dendro, level)
    # partition maps original node -> community id
    Q = community_louvain.modularity(partition, G)
    n_com = len(set(partition.values()))
    results.append((level, Q, n_com))
    print(f"{level:>5} {Q:>12.6f} {n_com:>14}")

# --- Save machine-readable copy too ---
import json
with open("results.json", "w") as f:
    json.dump({
        "graph": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges()},
        "params_used": p,
        "total_passes": len(dendro),
        "per_level": [{"level": l, "Q": q, "n_communities": c} for (l, q, c) in results],
    }, f, indent=2)
print("\nSaved results.json")
