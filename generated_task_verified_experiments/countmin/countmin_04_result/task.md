[Agents]

读给定材料，做实验，写结论。

自行复现 Count-Min Sketch（从给定材料中的论文出发用 Python/numpy 实现；`d` 个两两独立的哈希）。复现含更新与点查询；并实现 Count-Min 的 **heavy-hitter 识别**：流结束后，对所有出现过的 item 用 sketch 估计 `â[i]`，按 `â[i]` 从大到小取 top-`k`（或报告所有 `â[i] ≥ φ·‖a‖₁` 的 item 作为 heavy hitter）。

研究目标：**Count-Min 在 heavy-hitter / top-`k` 识别上的精确率（precision）与召回率（recall）如何随 sketch 大小（`w,d`）变化。**

固定实验设置（不要更改）：
- 数据流：**1e6** 次更新，**1e5** 个不同 item，**Zipfian（s≈1.0）**分布（天然产生少数高频 heavy hitter + 大量长尾 item）；记录真实频率 `a[i]`。
- 真实 top-`k`：按真实 `a[i]` 取 **k = 100** 个 heavy hitter 作为 ground truth。
- sketch 配置网格：**{ (w=512,d=3), (w=1024,d=5), (w=2048,d=5), (w=4096,d=8), (w=8192,d=10) }**（从小到大）。
- 识别规则：对每个配置，用 sketch 的 `â[i]` 取 top-`k=100`，与真实 top-`k` 比对，计算 **precision@k**（报告中真正属于真实 top-`k` 的比例）与 **recall@k**（真实 top-`k` 被找出的比例）。
- 每个配置用 **≥ 5 个不同哈希种子**独立重复，取均值。
- **仅 CPU**，单机；整轮 **< 30 分钟**。

把以下内容写到 `./summary_cm_04_heavy_hitter.md`：
1. 一张表：每个 `(w,d)` 配置下的 **precision@100** 与 **recall@100**（跨种子均值）。
2. 结论要点：sketch 越大（`w,d` 越大），precision 与 recall 是否越高并趋近 1；小 sketch 下是否出现**假阳性**（长尾 item 因被高估而挤进 top-`k`）导致 precision 下降；给出达到 precision、recall 都 ≥ 0.95 所需的最小 sketch 配置（近似）。

---

[Judge]

Look at `./summary_cm_04_heavy_hitter.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了每个 `(w,d)` 配置下的 **precision@100** 与 **recall@100**（跨 ≥5 种子均值），以表格呈现。
2. **precision 与 recall 随 sketch 增大而上升并趋近 1**：最小配置 `(512,3)` 的 precision 显著低于最大配置（小 sketch 下长尾 item 被高估挤入 top-`k` 造成假阳性）；最大配置下 precision 与 recall 都接近 1。
3. 明确给出达到 **precision ≥ 0.95 且 recall ≥ 0.95** 所需的（近似）最小 sketch 配置，并指出是 `w`（控单点高估）还是 `d`（控尾部失败）对消除 heavy-hitter 假阳性更关键（经验上 `w`/精度对 top-`k` 假阳性影响更大）。
