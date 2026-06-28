[Agents]

读给定材料，做实验，写结论。

用 Python + **NetworkX**。NetworkX 的 `betweenness_centrality(G, k=K)` 通过**只采样 `K` 个源（pivot endpoints）**对介数做近似（Brandes 算法的采样近似版）。`normalized=True` 时按采样规模归一化。

研究目标：**对比采样近似介数（不同样本量 `K`）与精确介数——验证近似误差随 `K` 增大而下降（约 `1/√K`），且带来显著加速。**

固定实验设置（不要更改）：
- 取一张中等规模图（如 NetworkX 生成的随机图或 `karate` 之外的 ~**1e3–1e4 节点**连通图），固定它作为基准。
- 先用 `k=None`（全部源）算**精确**介数 `BC_exact`。
- 采样量网格 **K ∈ {10, 50, 100, 500, min(n,2000)}**，对每个 `K` 调用 `betweenness_centrality(G, k=K)` 得近似 `BC_approx`。
- 对每个 `K`，记录：(a) 近似误差（如 `max_v |BC_approx − BC_exact|` 或 L1 误差）；(b) 运行时；(c) 用 **≥ 5 个不同种子**重复（采样源不同）取误差均值。
- 整轮 **< 30 分钟**。

把以下内容写到 `./summary_betweenness_04_sampling.md`：
1. 一张表：每个 `K` 下的近似误差（均值±标准差）与运行时，以及相对精确法的加速比。
2. 结论要点：近似误差是否随 `K` 增大而**下降**（量级约 `1/√K`：`K` ×4 → 误差约 ÷2）；小 `K` 下加速比显著（近似法只跑 `K` 个源而非 `n` 个）；给出"误差与精确法在可接受范围内、且远快于精确法"的折中 `K`。

---

[Judge]

Look at `./summary_betweenness_04_sampling.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了每个 `K ∈ {10,50,100,500,…}` 下采样近似的**误差**（如 max 绝对差，跨 ≥5 种子均值±标准差）与**运行时**，以表格呈现，并附相对精确法的加速比。
2. **近似误差随 `K` 增大而下降**，量级约 `1/√K`（`K` ×4 → 误差约 ÷2），实测趋势与之吻合（在一个不大的常数倍内）。
3. 小 `K` 下**加速比显著**（只跑 `K` 个源 vs 精确 `n` 个源，运行时约按 `K/n` 比例下降），并给出在所选图上一个"误差可接受且远快于精确法"的折中 `K` 取值。


---

[Judge V2]

查阅 `./summary_betweenness_04_sampling.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准）：

1. 须给完整表 K∈{10,50,100,500,2000}+精确、≥5 种子（golden：7 种子、偏差≈1e-6；可接受：≥5 种子、偏差 ≤1e-4 即无偏）。（细化原 [Judge] 第 1 点）
2. 须验证误差 ~1/√K（golden：斜率 max|err|=−0.525、RMSE=−0.506；可接受：斜率 ∈[−0.55,−0.45] 且误差·√K≈常数）。（细化原 [Judge] 第 2 点）
3. 须给小 K 加速 ≈n/K；折中 K=500（golden：max|err|≈1.2%、Top-20 0.95、Spearman 0.93、~6×快；可接受：K=500 时 max|err| ≤2%、Top-20 ≥0.9）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
