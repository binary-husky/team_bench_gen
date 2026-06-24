[Agents]

复现 RCMAES 算法（./material），配置 python 环境。

研究论文 §IV.C 中明确指出的 RCMAES 弱点：在 CEC2017 的 F29 上表现明显差于其他函数，导致 Friedman 排名受单函数拖累。论文用 ablation study（未公开发表）指出此问题但未深入分析。

至少做以下三件事，全部在 **CEC2017 D=30** 上跑（budget = 300000 evals）：

1. **故障量化**：在 F29 上跑 RCMAES 共 25 次，对比 RCMAES 在 F1-F28 上的平均 E（同样 25 次/run 中位数即可），量化 F29 的劣势倍数
2. **横向对比**：在 F29 上同时跑 RCMAES、LSRTDE（CEC2017 上 Friedman 排名第 1）、BIPOP-aCMAES 三个算法各 25 次，确认 RCMAES 在 F29 上的相对位置
3. **故障归因 + 缓解尝试**：F29 是 composition 函数（由多个子函数旋转平移组合而成）。尝试至少 3 种缓解策略并对比效果：
   - `larger_N0`：把 N0 公式（式 6）的系数放大 2 倍
   - `tighter_restart`：重启阈值从 1e-8 收紧到 1e-10，触发更频繁的重启探索不同 basin
   - `larger_exclusion`：把 exclusion region 从 10% 扩大到 30%，强制远离已收敛的局部最优

把故障分析（landscape 特征、收敛曲线、为什么 RCMAES 在 F29 上失败）和缓解策略效果对比写到 `./summary_f29_failure.md`。

---

[Judge]

Look at `./summary_f29_failure.md`, check whether conclusion cover the following points:

1. F29 上 RCMAES 的 E 至少是 F1-F28 平均 E 的 5 倍以上（量化劣势倍数）
2. F29 上 LSRTDE 的 E 比 RCMAES 至少低 50%（横向对比中 RCMAES 落后 LSRTDE）
3. 至少有 1 个缓解策略（larger_N0 / tighter_restart / larger_exclusion）能在 F29 上把 RCMAES 的 E 改善 ≥ 30%
4. 给出明确的失败归因（例如：F29 是多 basin composition，RCMAES 的种群缩减过快导致无法探索足够多的 basin；或 exclusion region 太小导致重启回到同一 basin 等）
