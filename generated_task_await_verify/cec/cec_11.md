[Agents]

复现 SHADE 算法（./material，含论文与参考实现），配置 python 环境。

研究 SHADE 相对经典 JADE 的**三个核心结构性创新**——并量化每个组件的边际贡献：

1. **历史记忆 M_CR, M_F（H 槽位）**：替代 JADE 的单点 μ_CR, μ_F（论文 §V.A 的核心创新）
2. **外部归档 A**：继承自 JADE，存档被淘汰的父代，从 P ∪ A 中选 r2（论文 §IV.B）
3. **每代随机 p**：替代 JADE 的静态 p（论文 §V.B 的次要创新）

通过 **2 × 2 × 2 = 8 个变体** 的完全因子消融（其他参数固定为论文默认：N=100, H=100, c=0.1 等价学习率, D=30, budget=300000），在以下 8 个 CEC2013 函数上跑 **25 次独立 run**（覆盖三种类型）：

- **unimodal**：F1（Sphere 类）, F5（Schwefel 类）
- **multimodal**：F9 (Rastrigin 类), F15 (Rastrigin 旋转), F19 (Schwefel 噪声)
- **composition**：F21, F25, F27

变体矩阵：

| 变体名 | 历史记忆 (H=100) | 外部归档 | 随机 p |
|------|---|---|---|
| `shade_full` | ✓ | ✓ | ✓ |
| `shade_no_mem` | ✗（单点 μ，c=0.1，退化为 JADE-style） | ✓ | ✓ |
| `shade_no_archive` | ✓ | ✗（\|A\|=0） | ✓ |
| `shade_static_p` | ✓ | ✓ | ✗（p ≡ 0.05 固定） |
| `shade_mem_archive_only` | ✓ | ✓ | ✗ |
| `shade_mem_randp_only` | ✓ | ✗ | ✓ |
| `shade_archive_randp_only` | ✗ | ✓ | ✓ |
| `jade_baseline` | ✗ | ✓ | ✗ |

把以下分析写到 `./summary_cec_11_component_ablation.md`：

1. **8 变体 × 8 函数的 SR 矩阵 + mean error 矩阵**
2. **边际效应分解**：对每个组件 C ∈ {mem, archive, randp}，计算 `Effect(C) = mean_error(shade_¬C) − mean_error(shade_full)` 在每个函数上的差值（正数 = 该组件减小 error；负数 = 该组件反而有害）。报告每个组件在 8 个函数上的边际效应分布
3. **协同 vs 替代**：是否有组件组合表现出超线性协同（`Effect(A,B) > Effect(A) + Effect(B)`）或互相替代（去掉任一影响不大）？
4. **诊断**：找出每个变体最"塌方"的函数，解释为什么（例：`shade_no_mem` 在 multimodal 上应明显劣化，因为单点 μ 容易被噪声样本污染）

---

[Judge]

阅读 `./summary_cec_11_component_ablation.md`，检查结论是否覆盖以下 3 个评价维度：

1. **历史记忆的边际贡献最大**：`shade_no_mem`（退化为 JADE-style 单 μ）在 multimodal 函数 F9, F15, F19 上的 mean error 比 `shade_full` 高至少 1 个数量级；在 composition 函数 F21, F25, F27 上 SR 比 `shade_full` 低 ≥ 20pp。这验证论文 §V.A 的核心论断——历史记忆是 SHADE 相对 JADE 的关键差异化。
2. **归档在多模态上有显著作用**：`shade_no_archive` 在至少 4/8 函数上 mean error 比 `shade_full` 高 ≥ 50%（参考论文 §IV.B 关于 archive 维持多样性的论断，该机制主要在多模态上发挥作用）。
3. **随机 p 是次要创新但非零贡献**：`shade_static_p` 在所有函数上与 `shade_full` 差距 ≥ 0 但通常 ≤ 1 个数量级，SR 差距 ≤ 15pp——证明随机 p 是一个"温和改进"，不像前两个组件那样决定性。如果某函数上 `shade_static_p` 反而比 `shade_full` 好（罕见），summary 中要识别并解释（可能是 p=0.05 对该函数更合适）。
