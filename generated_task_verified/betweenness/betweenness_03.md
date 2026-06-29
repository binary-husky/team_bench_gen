[Agents]

读给定材料，做实验，写结论。

用 Python + **NetworkX**（`betweenness_centrality`，Brandes O(nm)）。另实现一个**朴素基准**：对每个源 `s` 用 BFS 求 `σ[t]` 与所有 `s→t` 最短路列表，再对每对 `(s,t)` 逐节点累加 `σ_st(v)/σ_st`（约 O(n²·(n+m)) 或更慢，复杂度明显高于 Brandes）。

研究目标：**对比 Brandes O(nm) 与朴素法的运行时随图规模 `n` 的增长，验证 Brandes 的近线性（于 nm）优势。**

固定实验设置（不要更改）：
- 生成随机连通图（如 ER，固定平均度数使 `m = Θ(n)`），规模网格 **n ∈ {200, 500, 1000, 2000}**。
- 对每个 `n`：记录 (a) NetworkX Brandes 的运行时；(b) 朴素法的运行时（朴素法在大 `n` 下很慢，给一个**时间上限**如每点 ≤ ~2 分钟，超时则只记录 Brandes 并外推/标注朴素已不可行）。
- 每个规模用 **≥ 3 个不同种子**，取运行时中位数。
- 记录 `n`、`m`，以便把运行时表示为 `nm` 的函数。

把以下内容写到 `./summary_betweenness_03_runtime.md`：
1. 一张表/双对数图：每个 `n` 下 Brandes 与朴素法的运行时（秒）。
2. 结论要点：Brandes 运行时是否随 `nm` **近线性**增长（双对数斜率约 1，因 `m=Θ(n)` 即约随 `n²`）；朴素法增长明显更陡（约 `n³` 量级）；给出在某个 `n`（如 n=1000 或 2000）处 Brandes 相对朴素法的**加速比**。整轮 **< 30 分钟**。

---

[Judge]

Look at `./summary_betweenness_03_runtime.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 `n ∈ {200,500,1000,2000}` 下 **Brandes 与朴素法**的运行时（秒，跨 ≥3 种子取中位数），以表或双对数图呈现。
2. **Brandes 运行时随 `nm` 近线性增长**（`m=Θ(n)` 时双对数斜率约 2，即 Θ(n²)），而**朴素法增长更陡**（约 Θ(n³)），二者斜率明显不同。
3. 明确给出在较大规模（如 n=1000 或 2000）处 **Brandes 相对朴素法的加速比**（数倍～数量级），并指出朴素法在该规模已接近不可行而 Brandes 仍秒级——验证 O(nm) 的实用价值。


---

[Judge V2]

查阅 `./summary_betweenness_03_runtime.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准）：

1. 须给 Brandes vs 朴素运行时表 + 与 NetworkX 正确性（golden：max|Δ|=3.6e-14；可接受：≤1e-9）。（细化原 [Judge] 第 1 点）
2. 须给拟合斜率（golden：Brandes 1.10 vs nm、朴素 2.90 vs n；可接受：Brandes ∈[1.0,1.3]、朴素 ∈[2.7,3.1] 且二者分离）。（细化原 [Judge] 第 2 点）
3. 须给加速比随 n 增（golden：n=1000 ~11×、n=2000 ~18×；可接受：n=2000 加速 ≥10× 且 Brandes 秒级）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
