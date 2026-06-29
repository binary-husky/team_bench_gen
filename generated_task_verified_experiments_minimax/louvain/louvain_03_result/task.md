[Agents]

读给定材料，做实验，写结论。

考察社区数量与社区规模分布如何随图规模变化（层级展开）。数据：LFR 基准图，n ∈ {500, 1000, 2000, 4000}，其余参数固定（tau1=3, tau2=1.5, mu=0.4, average_degree=6, min_community=20, seed=0）。方法：对每个图运行 Louvain（community_louvain.best_partition(G, random_state=0)，或 networkx 的 louvain_communities(G, seed=0)）。记录：检测到的社区数、模块度 Q、按降序排列的社区规模分布、以及社区规模的基尼系数（或其他集中度指标）。把「社区数 / 模块度 / 规模分布 / 基尼系数 随 n 的变化」写到 ./summary_size_dist.md。固定设置：上述 LFR 参数与随机种子；唯一自变量为 n。

---

[Judge]

Look at `./summary_size_dist.md`, check whether conclusion cover the following points

1. 检测到的社区数随 n 增大而增多。
2. 模块度 Q 在不同 n 下都保持较高（例如 ≥0.7）且相对稳定。
3. 社区规模分布明显右偏/重尾（基尼系数偏高；少数大社区 + 一长尾小社区）。


[Judge V2]

查阅 `./summary_size_dist.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；LFR 固定参数/seed=0、n∈{500…4000}）：

1. 须给社区数随 n 增多（golden：k 15→20→22→35（n=500→4000）亚线性；可接受：随 n 增）。（细化原 [Judge] 第 1 点）
2. **重写/放宽原 [Judge] 第 2 点**：原判"Q ≥0.7"不成立——golden：Q 0.45→0.56→0.51→0.53（n=500→4000）、n≥1000 稳定 0.5–0.56；放宽为"Q 在 0.5–0.56 量级、随 n 饱和"（0.7 阈值对本 LFR 设置过高）。可接受：Q ≥0.45 且 n≥1000 稳定。（重写/放宽原 [Judge] 第 2 点）
3. 须给规模分布右偏重尾（golden：基尼 0.23→0.38、CV 0.43→0.70、最大社区 65→318 线性增、最小恒 1；可接受：基尼随 n 升、长尾）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
