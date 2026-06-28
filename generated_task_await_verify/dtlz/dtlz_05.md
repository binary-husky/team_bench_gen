[Agents]

读给定材料，做实验，写结论。

这是 DTLZ 课题中最深的扩展任务。论文 §6.8 描述了一个 DTLZ6/8/9 上独特的失效模式——**冗余解（redundant solutions）**：当真实 Pareto 前沿（曲线或低维曲面）与相邻表面弱非支配时，基于支配关系的 MOEA 最终种群里会保留大量不在真实前沿上的"看似非支配"解。论文只描述现象（图 6.30–6.31）但**没有**量化冗余比例或测试缓解策略。

本课题做两件事：

### Part A: 决策变量扩展性（DTLZ1 + DTLZ3, M=3）

固定 M=3，扫描决策变量维度 n ∈ {12, 32, 102, 302}（即 k ∈ {10, 30, 100, 300} 个 x_M 变量），在 DTLZ1 和 DTLZ3 上跑 NSGA-II，500 代，每个 (问题, n) 组合 **21 次独立 run**。

DTLZ1 的 g 函数（式 6.19）随 k 增大指数级增加局部前沿数（11^k − 1），DTLZ3 同样（3^k − 1）。论文 §6.7.1 与 §6.7.3 都说 "The problem can be made more difficult by using a larger k"，但**没有给出量化曲线**。请补充。

记录每个 (问题, n) 下的 IGD、HV、全局收敛成功率（g < 0.01）、平均 wall-clock 时间。

### Part B: 冗余解量化与缓解（DTLZ6 + DTLZ9）

固定 M=3, k=10, n=12, NSGA-II, 500 代, 31 次 run。

针对 DTLZ6 与 DTLZ9（论文 §6.8 明确点名的两个冗余问题），在每次 run 的最终种群（N=100）中：

1. **量化冗余比例**：定义 R := (种群中 "看似非支配" 但不在真实 Pareto 集合 ε-邻域内的解数) / N。ε 取 0.01（用 L2 距离）。论文 §6.8 说冗余问题在高维下更严重，请在 M ∈ {3, 5, 8} 上扫一遍 R vs M 的关系。
2. **缓解策略对比**：对每个问题 × 每个 M，对比 3 种 MOEA 变体：
    - `baseline`：标准 NSGA-II（拥挤距离）
    - `eps_dominance`：用 ε-dominance 替换标准 dominance（论文 §6.8 推荐，ε=0.05）
    - `shift_based_density`：用 shift-based density estimation 替换拥挤距离（论文未提，但学术界已知可缓解）

每个变体 × 问题 × M 跑 21 次，记录 R、IGD、HV。

把以下分析写到 `./summary_dtlz_05_redundancy_and_scaling.md`：

- Part A: 2 问题 × 4 n × 4 指标表 + 收敛成功率随 n 衰减曲线
- Part B: DTLZ6/9 的 R vs M 曲线（量化冗余随 M 增长）；3 个变体在 R 与 IGD 上的对比表
- 总结：决策变量维度灾难 vs 目标冗余问题——哪个对 NSGA-II 更致命？ε-dominance 与 shift-based density 谁更有效？

---

[Judge]

阅读 `./summary_dtlz_05_redundancy_and_scaling.md`，检查结论是否覆盖以下 3 个评价维度：

1. **Part A: DTLZ1/DTLZ3 的决策变量维度灾难**：DTLZ1 在 k=10 下的全局收敛成功率 ≥ 80%，在 k=100 下成功率 ≤ 20%（11^k 局部前沿指数增长使 NSGA-II 几乎必然卡局部前沿）；DTLZ3 退化更严重（k=100 下成功率 ≤ 5%）。Summary 必须给出 4 个 k 值下的具体成功率数字。Wall-clock 时间在 k=300 下应至少是 k=10 的 5 倍（计算量爆炸）。
2. **Part B: 冗余比例 R 随 M 单调上升**：DTLZ6 在 M=3 下 R ≤ 20%，M=5 下 R ≥ 40%，M=8 下 R ≥ 70%（参考论文 §6.8 "with the increase in the dimensionality of the objective space, the probability of occurrence of such redundant solutions is more"——必须复现这一单调上升）。DTLZ9 上同样模式但 R 略低（约束表面更紧）。
3. **Part B: ε-dominance 显著缓解冗余但牺牲多样性**：`eps_dominance` 变体在 DTLZ6 M=5 上的 R 比 baseline 低 ≥ 50%（如 baseline R=50%, eps R ≤ 25%）；但同时 IGD 可能略高（10–30% 范围内可接受），因为 ε-grid 强行离散化前沿损失精度。`shift_based_density` 在 IGD 上接近 baseline 但 R 仅小幅下降（≤ 30%）。Summary 必须基于数据明确推荐哪个缓解策略适合哪个场景（高维优先 ε-dominance 控冗余；中维优先 shift-based 保质量）。

---

## [Judge V2]（bcb94bc6 修订版 — 本实验超时，无法执行）

> 查阅 `./summary_dtlz_05_redundancy_and_scaling.md`。**如实记录**：本任务（Part A 决策变量扩展 k∈{10..300} + Part B 冗余解量化与 3 缓解策略，21-31 runs）orchestrator **超时**（`dtlz_05: TIMEOUT`）。无实测 golden。按"无法执行"放宽。

| 原 [Judge] 点 | 论文 golden / 已知结论 | 可接受范围（放宽） |
|---|---|---|
| 1. 决策变量维度灾难：DTLZ1 k=10 成功率 ≥80%、k=100 ≤20%；DTLZ3 更严重(≤5%)；k=300 耗时 ≥5× | 11^k/3^k 局部前沿指数增长 | 放宽：成功率随 k 下降方向一致即给分 |
| 2. 冗余比例 R 随 M 单调上升：DTLZ6 M=3 ≤20%、M=5 ≥40%、M=8 ≥70% | 论文 §6.8 | 放宽：R 随 M 上升方向一致即给分 |
| 3. ε-dominance 降冗余 R ≥50% 但 IGD 略升；shift-based 降幅小 | 论文 §6.8 推荐 | 放宽：给出"高维用 ε-dominance、中维用 shift-based"合理推荐即给分 |

> 总则：超时未完成；"维度灾难 + 冗余随 M 上升 + ε-dominance 控冗余"方向一致、推理自洽即通过。

<!-- judge-v2 authored-by: bcb94bc6 -->
