[Agents]

读给定材料，做实验，写结论。

考察 SimHash 估计在**极端余弦值（接近 +1 或接近 -1）**上的偏差与方差行为：估计器 `ĉ = cos(π·Hamming(bits_x, bits_y) / b)` 是否在高相似度 / 高度反相似区域出现**有符号偏差**或更大的方差。

固定实验设置（不要更改）：
- 用 NumPy 从零实现 SimHash（`sketch = sign(G @ v)`，G 为 b×d 随机高斯矩阵，固定 seed=12345）。
- 维度 d=100。
- 位数 b=256（让 RMSE 已经够小，方便观察 bias 而非噪声）。
- 生成 1000 对已知真实余弦 `c_true ∈ {-0.95, -0.9, -0.7, -0.5, -0.3, 0.0, 0.3, 0.5, 0.7, 0.9, 0.95}` 的随机向量对（用以下方式：随机选 v1 单位向量，再用 v2 = c·v1 + √(1−c²)·v_perp，其中 v_perp 是与 v1 正交的单位向量；固定 v_perp 的随机种子）。
- 对每对 (v1, v2) 计算 `ĉ`。
- **仅 CPU**；整轮 **< 10 分钟**。
- 提示：若 `sign(G@v)` 实现对 `0` 的处理不稳定，可加 `+ 1e-12` 后取 sign；该处理只影响 ~1/b 比例的位，不影响量级结论。

需要记录/报告的指标：
- 按 `c_true` 分桶（10 桶 + 极值桶 -0.95 / +0.95 单独），每桶 **mean(ĉ) / mean(ĉ - c_true) / RMSE**。
- 画一张 `c_true` vs `(mean(ĉ), RMSE)` 的图（双 y 轴或 2 子图）。
- 短结论：**估计器在高相似（c→+1）是否低估、高度反相似（c→-1）是否高估**（即"向 0 收缩"）？差值大小相对 RMSE 的占比。

把以上写到 `./summary_simhash_06_extreme_cosines.md`。

---

[Judge]

Look at `./summary_simhash_06_extreme_cosines.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了**每个 c_true 桶**（≥ 10 桶，含 ±0.95 极值桶）的 `mean(ĉ)`、`bias = mean(ĉ - c_true)`、`RMSE` 三项指标，以表 / 图呈现。
2. 明确指出**估计器是否存在"向 0 收缩"现象**——即在 c_true=+0.95 桶的 mean(ĉ) 显著小于 0.95（bias < -0.01）、c_true=-0.95 桶的 mean(ĉ) 显著大于 -0.95（bias > +0.01）；并报告此 bias 相对该桶 RMSE 的比例（通常 < 30%）。
3. 短结论明确说明**在 c_true=±0.95 处，RMSE 是否仍维持 O(1/√b) 量级**（与 _02 的同 d / 同 b 下的中段 RMSE 同量级或仅略大），并指出"高 |c| 区域的主要误差来自 bias 还是方差"。
