[Agents]

复现 JADE 算法（./material），配置 python 环境。

研究 JADE 两个核心组件的相互作用——**外部归档（archive）** 与 **greedy 变异策略 DE/current-to-pbest**——以及它们与 **参数自适应** 之间的协同关系（论文 §V.B 的核心声明：'JADE achieves remarkably better performance... a mutually beneficial cooperation between the greedy strategy and the parameter adaptation'）。

在以下 6 个 30 维基准函数上对比 **4 个变体**：

| 变体 | 变异策略 | archive | 参数自适应 |
|------|---------|---------|-----------|
| `jade_archive` | DE/current-to-pbest (eq. 7) | ✓ | ✓ |
| `jade_no_archive` | DE/current-to-pbest (eq. 6, |A|=0) | ✗ | ✓ |
| `rand_jade` | DE/rand/1（替换 eq. 6/7 的 current-to-pbest） | ✗ | ✓ |
| `nona_jade` | DE/current-to-pbest (eq. 6) | ✗ | ✗（μ_F = μ_CR = 0.5 固定） |

测试函数（覆盖 unimodal / 窄谷 / 多模态）：**f1 (Sphere), f3 (Schwefel 1.2), f5 (Rosenbrock), f9 (Rastrigin), f10 (Ackley), f11 (Griewank)**。

每个 变体 × 函数 组合跑 **30 次独立 run**（50 次更好但 30 次够看趋势），用论文 §V.A 的标准 generation 数。成功阈值 1e-8（f5 用 1e-1）。

把以下分析写到 `./summary_component_ablation.md`：

1. 6 函数 × 4 变体 的 SR 矩阵和 mean final error 矩阵
2. 计算 "互协同度" 指标：`JADE_full - max(JADE_no_archive, rand_jade, nona_jade)` 在每个函数上的 SR 差距（单位 pp）。论文 §V.B 声明 JADE_full 应显著优于任一变体。
3. 找出每个变体最"塌方"的函数，解释为什么（例如：rand_jade 在 f3 上 SR=38% 是因为 DE/rand/1 在 ill-conditioned Hessian 下不能维持多样性，参考论文 §V.B 的原文解释）

---

[Judge]

阅读 `./summary_component_ablation.md`，检查结论是否覆盖以下 3 个评价维度：

1. **rand_jade 在窄谷 / ill-conditioned 函数上塌方**：rand_jade 在 f3 的 SR ≤ 60%（论文 Table VI 报告 38%），在 f5 的 SR = 0%（论文报告 0%）。这一现象是论文 §V.B 解释的"DE/rand/1 在 ill-conditioned Hessian 下不能维持多样性"的直接体现。
2. **nona_jade 在维度敏感函数上塌方**：nona_jade 在 f4-equivalent（这里测 f9 / f10 等多模态函数）的 SR 比 jade_no_archive 低 ≥ 20pp（论文 Table VI 报告 nona_jade 在 f4 的 SR=0%、f9 SR=0%、f8 SR=16%，而 jade_no_archive 都是 100%）。说明去掉参数自适应会显著损伤多模态函数上的可靠性。
3. **JADE_full 的"协同放大"效应**：在至少 4/6 个测试函数上，`jade_archive` 的 SR 比 `max(jade_no_archive, rand_jade, nona_jade)` 高 ≥ 5pp（即"组合优于任一组件"）。若该效应在某些函数上不成立（例如 f1 上几个变体都接近 100% SR），summary 中要识别并解释这些 plateau 情况。

---

## [Judge V2]（bcb94bc6 修订版 — 本实验超时，无法执行）

> 查阅 `./summary_component_ablation.md`。**如实记录**：本任务（JADE 组件消融：rand_jade / nona_jade / jade_no_archive / full × 6 函数）orchestrator **超时**（`jade_03: TIMEOUT`）。无实测 golden。按"无法执行"放宽。

| 原 [Judge] 点 | 论文 golden / 已知结论 | 可接受范围（放宽） |
|---|---|---|
| 1. rand_jade 在 ill-conditioned 塌方：f3 SR ≤60%(论文 38%)、f5 SR=0% | 论文 Table VI / §V.B | 放宽：rand_jade 在窄谷函数 SR 大幅下降方向一致即给分 |
| 2. nona_jade 多模态 SR 比 jade_no_archive 低 ≥20pp | 去自适应损可靠性 | 放宽：nona_jade 多模态更差方向一致即给分 |
| 3. full 协同放大：≥4/6 函数 SR 比 max(组件) 高 ≥5pp | 组合优于组件 | 放宽：full 多数函数不差于任一组件即给分 |

> 总则：超时未完成；"去 rand/去自适应 在特定函数塌方、full 协同最强"方向一致、推理自洽即通过。

<!-- judge-v2 authored-by: bcb94bc6 -->
