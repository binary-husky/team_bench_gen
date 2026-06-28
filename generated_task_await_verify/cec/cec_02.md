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

---

## [Judge V2]（bcb94bc6 修订版 — 本实验超时，无法执行）

> 查阅 `./summary_cross_benchmark.md`。**如实记录**：本任务（RCMAES 在 CEC2017 D=30 / CEC2020 D=20 / CEC2022 D=20 三套基准、每函数 25 runs、Friedman 排名）在 orchestrator 中**超时**，记录于 `.verify_judge/_skipped.txt`（`cec_02: TIMEOUT — exceeded budget`）。本环境**未产出 summary**，无实测 golden 值。按"无法执行"处理：放宽为言之有理即给分，golden 取论文报告值。

| 原 [Judge] 点 | 论文 golden | 可接受范围（放宽） |
|---|---|---|
| 1. CEC2017 D=30 的 E | 0.071 | 原区间 [0.04, 0.10]；放宽：E 量级落在 ~0.05–0.10、方向一致即给分 |
| 2. CEC2020 D=20 的 E | 0.024 | 原 [0.015, 0.035]；放宽：量级一致（~0.02）即给分 |
| 3. CEC2022 D=20 的 E | 0.016 | 原 < 0.025；放宽：低 E（< 0.05）即给分 |
| 4. Friedman 排名 | RCMAES 在 ≥2/3 基准上 ≤ BIPOP-aCMAES | 放宽：给出排名、RCMAES 有竞争力（不垫底）即给分 |

> 总则：实验超时未完成；若 solver 基于论文/部分实验给出方向一致、量级合理、推理自洽的结论，按通过计。

<!-- judge-v2 authored-by: bcb94bc6 -->
