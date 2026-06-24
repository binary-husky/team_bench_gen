[Agents]

复现 RCMAES 算法（./material），配置 python 环境。

研究 RCMAES 的跨基准鲁棒性：在三个 CEC 基准套件上分别复现，验证论文中"RCMAES 在所有基准上保持稳定表现"的核心声明。

至少覆盖以下三个基准设置：
1. **CEC2017 D=30**（CEC2026 竞赛设置）：budget = D × 10000 = 300000 evals，共 29 个函数
2. **CEC2020 D=20**：budget = D × 5000 = 100000 evals，共 22 个函数
3. **CEC2022 D=20**：budget = D × 2000 = 40000 evals，共 12 个函数

每个设置下每个函数跑 25 次独立 run（用 run index 作为随机种子）。

按照论文 §IV.B 的评分方法学，对每个基准分别计算：
- accuracy-based metric E = mean_j( ε_jk / (1 + ε_jk) )，其中 ε_jk = (f - f*) / f*
- 在 RCMAES 与 BIPOP-aCMAES、ARRDE、LSRTDE 三个 baseline 之间做 Friedman 排名

把每个基准下的 E、Friedman 排名、与论文报告值的对比写到 `./summary_cross_benchmark.md`。

---

[Judge]

Look at `./summary_cross_benchmark.md`, check whether conclusion cover the following points:

1. CEC2017 D=30 下 RCMAES 的 E 值落在 [0.04, 0.10] 区间内（论文报告 0.071）
2. CEC2020 D=20 下 RCMAES 的 E 值落在 [0.015, 0.035] 区间内（论文报告 0.024）
3. CEC2022 D=20 下 RCMAES 的 E 值 < 0.025（论文报告 0.016）
4. 至少在 2/3 个基准上，RCMAES 的 Friedman 排名不超过 BIPOP-aCMAES
