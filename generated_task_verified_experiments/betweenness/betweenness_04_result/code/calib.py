import networkx as nx
import time
import random

# Benchmark exact betweenness on a connected graph of various sizes
for n in [1000, 2000, 3000]:
    random.seed(42)
    G = nx.barabasi_albert_graph(n, 3, seed=42)
    G = max((G.subgraph(c) for c in nx.connected_components(G)), key=len)
    n2 = G.number_of_nodes(); m2 = G.number_of_edges()
    t0 = time.perf_counter()
    bc = nx.betweenness_centrality(G, k=None, normalized=True)
    dt = time.perf_counter() - t0
    print(f"BA n={n}->cc n={n2}, m={m2}: exact BC time = {dt:.2f}s")
