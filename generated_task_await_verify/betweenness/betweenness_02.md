[Agents]

读给定材料，做实验，写结论。

用 Python + **NetworkX**（`networkx.betweenness_centrality`，即 Brandes 的标准 O(nm) 实现）计算介数。另**自行实现一个朴素基准**：对小图枚举所有节点对 `(s,t)`，用 BFS 求出 `s→t` 的全部最短路，对每个中间节点 `v` 累加 `σ_st(v)/σ_st`。

研究目标：**验证 Brandes（NetworkX）算出的介数与朴素逐对最短路计数的结果完全一致（正确性核对）。**

固定实验设置（不要更改）：
- 测试图集（均较小，因朴素法开销大）：Zachary 空手道俱乐部图，以及若干随机图（如 ER 与连通随机图，**n ∈ {15, 20, 30, 50}**，多取几个边密度），共 **≥ 10** 张图。
- 对每张图，分别用 (a) NetworkX Brandes、(b) 朴素逐对计数算每个节点的介数（注意无向图对 (s,t) 与 (t,s) 去重，且排除端点；归一化与否两版需一致）。
- 用 **≥ 3 个不同随机种子**生成随机图。

需要记录/报告的指标：
- 两方法每个节点的介数**最大绝对差** `max_v |BC_brandes(v) − BC_naive(v)|`（应为 **≈ 0**，允许浮点级容差如 1e-9）。

把以下内容写到 `./summary_betweenness_02_correctness.md`：
1. 一张表：每张图的节点数、边数、两方法的最大绝对差。
2. 结论要点：在所有测试图上，Brandes 与朴素法结果是否**逐节点一致**（最大绝对差在浮点容差内），验证 Brandes 的依赖累加是正确的（与"对每对 (s,t) 显式数最短路"等价）。

---

[Judge]

Look at `./summary_betweenness_02_correctness.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 **≥10 张测试图**（含 Zachary 空手道 + 多张随机图，n∈{15..50}）下，NetworkX Brandes 与朴素逐对最短路计数结果的**每节点最大绝对差**，以表格呈现（基于 ≥3 种子）。
2. **所有图上最大绝对差都在浮点容差内（≈ 0，如 ≤ 1e-9）**——Brandes 与朴素法逐节点一致，验证 Brandes 依赖累加正确。
3. 归一化/无向去重处理一致（两方法在同一约定下比对），排除"约定不同导致的假不一致"，确保差异确实反映算法正确性。
