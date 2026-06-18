[Agents]

复现 RCMAES 算法（./material），配置 python 环境。

研究 RCMAES 的边界约束处理（bound constraint handling）策略。论文 §III 采用 stochastic repair（在违反边界附近的截断区间内重采样）。固定其他部分与 paper 默认一致。

至少对比以下 5 种边界处理策略，全部在 **CEC2022 D=20**（budget = 40000 evals）上跑：

1. `stochastic_repair`（paper）：违反边界的坐标在边界附近截断区间内重采样（区间宽度由违反量决定）
2. `clip`：直接 clamp 到边界
3. `reflect`：以边界为对称轴反射回可行域
4. `wrap`：toroidal wrap（模运算把越界点映射回可行域）
5. `resample`：在整条边界 [L, U] 内均匀重采样整个个体

每个策略在全部 12 个 CEC2022 D=20 函数上跑 25 次。

记录每种策略下：final E、收敛曲线、最优解距离最近边界的平均距离（用于诊断是否陷入边界）。

把结论写到 `./summary_bound_handling.md`。

---

[Judge (IQ requirement: low-IQ)]

Look at `./summary_bound_handling.md`, check whether conclusion cover the following points:

1. stochastic_repair（paper）在 overall E 上排第 1，或与第 1 差距 ≤ 3%
2. clip 策略在 multimodal 函数 F10-F12 上明显劣于 stochastic_repair（E 差距 ≥ 10%），且最优解距离边界更近（说明陷入边界）
3. wrap 与 reflect 与 stochastic_repair 性能接近（overall E 差距 ≤ 10%）
4. resample（整域重采样）在所有函数上都最差（E 至少是 stochastic_repair 的 1.5 倍）
