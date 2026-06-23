[Agents]

复现 SHADE 算法（./material，含论文与参考实现），配置 python 环境（numpy + scipy 即可；CEC2013 测试函数可用现成 python 移植，例如 `pip install cec2013-functions` 或同等实现）。

按论文 §V 与 §VI.A 的标准参数复现 SHADE 在 **CEC2013 D=30**（budget = D × 10000 = 300000 evals，51 runs，搜域 [-100, 100]^D，error threshold 1e-8）上的完整结果：

- N = 100（种群规模）
- H = 100（记忆规模）
- p ~ U[2/N, 0.2] = U[0.02, 0.2]（每个个体每代独立采样）
- archive 大小 = N，溢出时随机删除
- 边界处理：中点修复（论文式 21）
- 控制参数采样：`CR_i ~ N(M_CR[r_i], 0.1)` 截断到 [0,1]；`F_i ~ C(M_F[r_i], 0.1)`，>1 截到 1、≤0 重采样
- 记忆更新：`mean_WA(S_CR)`（按 ∆f 加权算术均值）与 `mean_WL(S_F)`（按 ∆f 加权 Lehmer 均值），循环索引 k

同时实现一个 `DE/rand/1/bin` baseline（F=0.5, CR=0.9, NP=100）作为参照，验证 SHADE 的相对加速比。

把以下结果写到 `./summary_cec_10_basic_repro.md`：

1. **完整 28 函数表**：SHADE 与 DE/rand/1 的 mean ± std error，对照论文 Table I 的 SHADE 报告值（计算 repro/paper 比值）
2. **按函数类型分组汇总**：unimodal F1–F5 / multimodal F6–F20 / composition F21–F28，分别报告 SHADE 在每组上的几何平均 error 与 SR（成功率，threshold=1e-8）
3. **横向 Wilcoxon 检验**：把复现的 SHADE 与复现的 DE/rand/1 做 Wilcoxon rank-sum test（p<0.05），统计 +/−/≈ 数（以 SHADE 为基准）
4. **诊断**：找出复现偏差最大的 1–2 个函数（repro/paper 比值离 1 最远），分析偏差来源（CEC2013 实现差异 / 随机种子数 / 浮点精度等）

---

[Judge (IQ requirement: low-IQ)]

阅读 `./summary_cec_10_basic_repro.md`，检查结论是否覆盖以下 3 个评价维度：

1. **数值复现合理**：SHADE 在 unimodal F1–F5 上的 mean error 与论文 Table I 报告值的比值落在 `[0.1, 10]` 区间内（即一个数量级以内）；F1, F5, F11 这种 SHADE 报告 0 的函数，复现值也应 ≤ 1e-8（视为 0）。
2. **SHADE 显著优于 DE/rand/1**：在至少 22/28 函数上 SHADE 的 mean error 比 DE/rand/1 低（参考论文 Table I 与 §VI.A 的论断——SHADE 在 unimodal 与 multimodal 上表现最好；composition 上稍弱但仍优于经典 DE）；Wilcoxon 检验 "-"（DE 显著差于 SHADE）的计数 ≥ 20。
3. **composition 函数上的相对弱点**：在 F21–F28（composition）至少 3 个函数上，SHADE 的 repro mean error 落在 `[1e+1, 1e+3]` 数量级（论文报告 dynNP-jDE 在 composition 上比 SHADE 略好，但 SHADE 仍是 DE 系列中前列）——若复现值明显优于论文（< 1e-1）需在 summary 中给出可疑来源说明。
