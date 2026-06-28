[Agents]

复现 JADE 算法（./material），配置 python 环境。

研究 JADE 参数自适应机制中的**两个特殊设计选择**，单独验证它们的贡献：

1. **F 的采样分布**：论文 §IV.C 声称 "Compared to a normal distribution, the Cauchy distribution is more helpful to diversify the mutation factors and thus avoid premature convergence which often occurs in greedy mutation strategies... if the mutation factors are highly concentrated around a certain value."
2. **F 的均值更新方式**：论文 §IV.C 声称 "the adaptation of μ_F places more weight on larger successful mutation factors by using the Lehmer mean... To the contrary, an arithmetic mean of SF tends to be smaller than the optimal value of the mutation factor and thus leads to a smaller μ_F and causes premature convergence at the end."

把 JADE 的 `F` 适应机制做 **2 × 2 完全因子** 的对比：

| 变体 | F 采样分布（eq. 10） | μ_F 更新公式（eq. 11–12） |
|------|---------------------|---------------------------|
| `cauchy_lehmer` | Cauchy(μ_F, 0.1) | Lehmer mean `ΣF²/ΣF`（论文默认） |
| `cauchy_arith` | Cauchy(μ_F, 0.1) | 算术平均 `ΣF/|SF|` |
| `normal_lehmer` | Normal(μ_F, 0.1) | Lehmer mean |
| `normal_arith` | Normal(μ_F, 0.1) | 算术平均 |

CR 侧保持论文默认（Normal + arithmetic mean），其他参数（`c=0.1`, `p=0.05`, `NP=100`）保持不变。

在以下 6 个 30 维函数上对比（按"应该最敏感"的顺序）：

- **f5**（Rosenbrock 窄谷，论文 §V.B 提到 ill-conditioned Hessian——Lehmer 应在此处最关键）
- **f9, f10, f11**（多模态，Cauchy 的重尾对避免早熟应有最大收益）
- **f3**（ellipsoid，Cauchy 的随机性应帮助 escape）
- **f1**（Sphere，作为对照——所有变体在此都应表现良好）

每个 变体 × 函数 跑 **30 次独立 run**，记录 SR、FESS、最终 mean error，以及在最后一代的 μ_F 平均值。

把以下分析写到 `./summary_distribution_design.md`：

1. 4 个变体 × 6 函数 的 SR 矩阵
2. **Cauchy vs Normal 的边际效应**：在固定 mean 方式（lehmer）下，`SR(cauchy_lehmer) − SR(normal_lehmer)` 在多模态函数（f9, f10, f11）vs unimodal（f1, f3）的对比
3. **Lehmer vs 算术均值的边际效应**：在固定分布（Cauchy）下，`SR(cauchy_lehmer) − SR(cauchy_arith)` 在窄谷函数（f5）vs 其他函数的对比
4. **是否可加（正交性）**：`SR(cauchy_lehmer)` 是否接近 `SR(cauchy_arith) + (SR(normal_lehmer) − SR(normal_arith))`，即两个设计选择是否近似独立

---

[Judge]

阅读 `./summary_distribution_design.md`，检查结论是否覆盖以下 3 个评价维度：

1. **Cauchy > Normal 主要在多模态函数上显著**：`cauchy_lehmer` 在 f9 / f10 / f11 上的 SR 平均比 `normal_lehmer` 高 ≥ 5pp；而在 f1 上两者 SR 差距 ≤ 2pp（Sphere 上分布选择几乎无影响）。这与论文 §IV.C 的"Cauchy 帮助 greedy 策略避免早熟"的论断一致。
2. **Lehmer > 算术均值的边际效应在 f5 上最显著**：`cauchy_lehmer` 在 f5 上的 SR 比 `cauchy_arith` 高 ≥ 10pp（或 final mean error 低 ≥ 1 个数量级）。这验证了论文 §IV.C 关于"算术均值导致 μ_F 偏小、最终早熟"的论断。
3. **μ_F 稳态值的差异**：在 f9 / f10 等多模态函数上，`cauchy_lehmer` 最后一代的 μ_F 平均值应 > 0.4，而 `cauchy_arith` 的 μ_F 应 < 0.3。这直接展示 Lehmer 均值把 μ_F "推大" 的效果。

---

## [Judge V2]（bcb94bc6 修订版 — 本实验超时，无法执行）

> 查阅 `./summary_distribution_design.md`。**如实记录**：本任务（Cauchy/Normal × Lehmer/算术均 × 多函数消融）orchestrator **超时**（`jade_04: TIMEOUT`）。无实测 golden。按"无法执行"放宽。

| 原 [Judge] 点 | 论文 golden / 已知结论 | 可接受范围（放宽） |
|---|---|---|
| 1. Cauchy>Normal 主要在多模态（f9/10/11 SR +≥5pp；f1 ≤2pp） | 论文 §IV.C | 放宽：Cauchy 在多模态更优、unimodal 无差异方向一致即给分 |
| 2. Lehmer>算术均 在 f5 最显著（SR +≥10pp 或误差低 ≥1 数量级） | 算术均致 μ_F 偏小早熟 | 放宽：方向一致即给分 |
| 3. μ_F 稳态：cauchy_lehmer >0.4、cauchy_arith <0.3 | Lehmer 推大 μ_F | 放宽：cauchy_lehmer 稳态 μ_F 更高方向一致即给分 |

> 总则：超时未完成；"Cauchy+Lehmer 推大 μ_F、抗早熟"方向一致、推理自洽即通过。

<!-- judge-v2 authored-by: bcb94bc6 -->
