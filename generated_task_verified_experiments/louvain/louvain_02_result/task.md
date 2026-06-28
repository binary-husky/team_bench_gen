[Agents]

读给定材料，做实验，写结论。

考察 Louvain 在多轮（pass）迭代中模块度如何收敛。数据：用 networkx 生成的 LFR 基准图（LFR_benchmark_graph, n=1000, tau1=3, tau2=1.5, mu=0.4, average_degree=6, min_community=20, seed=0；若该参数生成失败可微调 average_degree/min_community，保持小规模）。方法：用 python-louvain 的 generate_dendrogram(G, random_state=0) 得到逐轮划分序列（dendrogram 的每一层 = 一个 pass 之后的划分）；对每一层用 partition_at_level 映射回原始节点，并用 community_louvain.modularity 计算该层的模块度 Q，同时记录该层的社区数。把「每一轮的 Q 与社区数」以及「总轮数、收敛趋势」写到 ./summary_convergence.md。固定设置：上述 LFR 参数与 random_state=0；唯一考察对象是 pass 轮次。

---

[Judge]

Look at `./summary_convergence.md`, check whether conclusion cover the following points

1. 模块度 Q 随 pass 轮次上升并在少数轮后趋于平台（已收敛）。
2. 社区数随 pass 轮次下降（聚合阶段把小社区合并）。
3. 通常在很少的轮次（例如 ≤5）内即收敛，之后再无提升。
