[Agents]

读给定材料，做实验，写结论。

考察分辨率参数 γ（resolution）对社区划分粒度的影响。数据：LFR 基准图（n=1000, tau1=3, tau2=1.5, mu=0.4, average_degree=6, min_community=20, seed=0）。方法：分别以 resolution γ ∈ {0.5, 1.0, 1.5, 2.0} 运行 Louvain（best_partition(G, random_state=0, resolution=γ)，或 networkx 的 louvain_communities(G, seed=0, resolution=γ)）。对每个 γ 记录：社区数、平均社区规模、以及用标准（γ=1）公式计算的模块度 Q（便于在同一标准下横向比较）。把「社区数 / 平均规模 / 标准模块度 随 γ 的变化」写到 ./summary_resolution.md。固定设置：上述 LFR 参数与随机种子；唯一自变量为 γ。

---

[Judge]

Look at `./summary_resolution.md`, check whether conclusion cover the following points

1. γ 增大（>1）时社区数增多、平均社区规模变小（划分更细）。
2. γ 减小（<1）时社区数减少、社区变大（发生合并）。
3. 用标准（γ=1）模块度衡量时，γ=1 取得最高值，γ 偏离 1 时标准模块度下降。
