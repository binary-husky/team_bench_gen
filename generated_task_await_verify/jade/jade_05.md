[Agents]

复现 JADE 算法（./material），配置 python 环境。

这是 JADE 课题中最深的诊断 / 扩展任务。要做两件事：

### Part A: 动力学诊断（复现论文 Figure 4）

在以下 4 个 30 维函数上跑 JADE w/ archive（标准参数），每代记录 `μ_F` 与 `μ_CR` 的轨迹，跑 **30 次独立 run**，绘制 `mean ± std-error` 曲线（横轴 generation，纵轴 μ_F 或 μ_CR）：

- **f1**（Sphere）：论文 §V.C 称 "μ_F and μ_CR change little"
- **f3**（Schwefel 1.2 ellipsoid）：论文称 "go to steady states after obvious initial changes"
- **f5**（Rosenbrock）：论文称 "μ_F and μ_CR reach steady states after the population falls into the narrow valley"
- **f9**（Rastrigin）：论文称 "the landscape shows different shapes as the algorithm proceeds and thus μ_F and μ_CR evolve to different values accordingly"

把 4 张 μ_F 曲线 + 4 张 μ_CR 曲线（共 8 张）保存到 `./dynamics_plots/` 下，并在 summary 中定性描述每条曲线的形状（平直 / 早期突变后稳态 / 振荡）。

### Part B: 参数敏感性扩展（push 超出论文推荐的 [5%, 20%] 区间）

论文 §IV.D 称 "JADE usually performs best with `1/c ∈ [5, 20]` and `p ∈ [5%, 20%]`"，但没有系统报告**超出**该推荐区间的失败模式。请扩展：

**固定函数 f5 (Rosenbrock)** 和 **f10 (Ackley)**，做两组单变量 sweep：

1. **`p` sweep**：固定 `c = 0.1`，扫 `p ∈ {1%, 5%, 10%, 20%, 30%, 50%, 80%}`（7 个值），记录 SR 与最终 mean error
2. **`c` sweep**：固定 `p = 0.05`，扫 `1/c ∈ {1, 2, 5, 10, 20, 50, 100}`（即 c ∈ {1, 0.5, 0.2, 0.1, 0.05, 0.02, 0.01}，7 个值），记录 SR 与最终 mean error

每个 (函数, p, c) 组合跑 **20 次独立 run**（参数 sweep 共 2 函数 × 7 p × 20 = 280 runs + 2 函数 × 7 c × 20 = 280 runs，共 560 runs）。

把所有分析写到 `./summary_dynamics_sensitivity.md`，包含：

- Part A 的 4 张 μ_F + 4 张 μ_CR 曲线（嵌入或链接 `./dynamics_plots/`）
- Part B 的 2 张 p-sweep SR 曲线 + 2 张 c-sweep SR 曲线
- 论文推荐区间 `[5%, 20%] × [5, 20]` 内 vs 区间外的 SR 显著性检验（如 Wilcoxon 或简单差值）

---

[Judge (IQ requirement: medium-IQ)]

阅读 `./summary_dynamics_sensitivity.md`，检查结论是否覆盖以下 3 个评价维度：

1. **Part A：动力学曲线定性匹配论文 Figure 4**：
    - f1 的 μ_F / μ_CR 曲线在 [0.4, 0.6] 间小幅波动，整体接近平直（标准差 ≤ 0.1）。
    - f3 / f5 的曲线呈现"早期明显变化 → 后期稳态"的形状（前 ~20% generations 内 μ_F 移动 ≥ 0.1，之后稳定）。
    - f9 的曲线呈现持续振荡（μ_F 的 std 在整个过程中都 > 0.05）。
    - 这一定性模式必须出现在 summary 中，与论文 §V.C 的描述对应。
2. **Part B：p-sweep 边界验证**：p 在 [5%, 20%] 内 SR 接近最大值（差 ≤ 5pp），p = 80% 时 SR 比 p = 5% 低 ≥ 15pp（验证 "p 太大会过于 greedy，损害多样性"——论文 §IV.D 提到的 "the latter is too greedy to maintain the diversity of the population"）。p = 1% 在 f5 上也应有 SR 下降（论文 §IV.D 提到 "p · NP = 1 ... may lead to less satisfactory results"）。
3. **Part B：c-sweep 边界验证**：1/c = 1（即 c = 1）时 SR 比 1/c = 10 低 ≥ 10pp（验证 "small value of 1/c causes false convergence due to the lack of sufficient information to smoothly update CR and F"）；1/c = 100 时也应出现 SR 下降（c 太小导致 lifetime 太长，无法跟上问题 landscape 的变化）。两端的"U 形"曲线必须出现。
