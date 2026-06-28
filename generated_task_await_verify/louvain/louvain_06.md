[Agents]

读给定材料，做实验，写结论。

考察 **边权** 对 Louvain 社区检测的影响：同一图在无权 / 加权下产生的社区数、模块度、NMI 是否一致——验证 Blondel et al. 2008 §III.B 描述的"weighted version is the default formulation, unweighted is the special case w=1"在实测中是否成立。

固定实验设置（不要更改）：
- 数据：
  - **Karate**（nx.karate_club_graph，34 节点，已有"真实"社区标签——`club` 属性）；
  - **LFR**：`nx.LFR_benchmark_graph(n=1000, tau1=3, tau2=1.5, mu=0.3, average_degree=10, min_community=20, seed=42)`，已有真实社区标签；
  - **加权变体**：对 Karate 与 LFR 各构造一个**加权版本**——给每条边赋 `w = 1 + 3·|hash(u+v) mod 100| / 100`（值域 [1, 4] 的伪随机正权），固定 seed。
- 算法：`networkx.algorithms.community.louvain_communities` / `python_louvain`，对每个图分别以**无权 / 加权**两种方式跑。
- 指标：
  - 社区数 `|C|`；
  - 模块度 `Q = nx.community.modularity(G, communities, weight=...)`；
  - 对 Karate：与 `club` 标签的 NMI（`sklearn.metrics.normalized_mutual_info_score`）；
  - 对 LFR：与 `communities` 真实社区的 NMI。
- 每个 `(图, 加权方式)` 用 **≥ 5 个不同随机种子**独立重复（louvain 自身有随机性）。
- **仅 CPU**；整轮 **< 15 分钟**。

需要记录/报告的指标：
- 一张表：`(Karate, LFR) × (无权, 加权)` 的 4 个 cell，每个 cell 给出 `|C|`、`Q`、NMI（Karate/LFR）的均值 ± 标准差（≥ 5 种子）。
- 短结论：**加权相对无权是否在 Q / NMI 上带来可测改善或退化**（一般加权会改变 Q 数值但不改变 NMI 与社区数，量级一致即视为"加权是通用化、无偏"）；以及 Karate 在加权下 Q 是否**单调非降**（无权 Q → 加权 Q 不下降）。

把以上写到 `./summary_louvain_06_weighted.md`。

---

[Judge]

Look at `./summary_louvain_06_weighted.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 `Karate × {无权, 加权}`、`LFR × {无权, 加权}` 四个 cell 的 `|C|`、`Q`、NMI 均值 ± 标准差（≥ 5 种子），以表格呈现。
2. 短结论明确**加权相对无权在 Q 上是否单调非降**（如无权 Q=0.41、加权 Q=0.42 类似量级即视为"无退化"）；NMI 在 Karate/LFR 上**加权 vs 无权 ≤ 0.05 差值**（即加权不破坏社区身份识别）。
3. 加权情况下 `|C|` 变化幅度（加权/无权）|Δ|/|C_unweighted| ≤ 20%（即加权对社区数不构成破坏）。
