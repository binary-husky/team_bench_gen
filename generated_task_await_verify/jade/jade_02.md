[Agents]

复现 JADE 算法（./material/jade_paper_original.pdf 或 ./material 中的参考实现），配置 python 环境（numpy 即可）。

按论文 §IV 的标准参数（`c = 0.1`, `p = 0.05`, `μ_F = μ_CR = 0.5` 初始化，`NP = 100` 在 D = 30 时），在以下 4 个 30 维基准函数上独立实现 JADE **with archive**（即采用公式 7 的 `DE/current-to-pbest/1 with archive` 变异策略）：

- **f1**：Sphere，`[-100, 100]^D`，最优值 0
- **f3**：Schwefel 1.2（ellipsoid / 旋转 unimodal），`[-100, 100]^D`，最优值 0
- **f5**：Rosenbrock（窄谷），`[-30, 30]^D`，最优值 0
- **f9**：Rastrigin（多模态），`[-5.12, 5.12]^D`，最优值 0

每个函数运行 **50 次独立 run**，使用与论文 Table IV 一致的 generation 数（f1=1500, f3=5000, f5=3000, f9=1000+5000）。

成功阈值：除 f5 用 1e-1（Rosenbrock 在 D=30 下很难精确收敛）外，其余函数用 1e-8。

把以下结果写到 `./summary_basic_repro.md`：

1. 每个函数下 JADE w/ archive 的最终 mean ± std error、SR（success rate, %）、FESS（成功 run 的平均函数评估次数）
2. 与论文 Table IV 中 "JADE with archive" 行的直接对比（paper 值 vs repro 值，比值或差值）
3. 同时实现一个经典 `DE/rand/1/bin` baseline（`F = 0.5`, `CR = 0.9`）作为参照，对比 JADE 的加速比

---

[Judge (IQ requirement: low-IQ)]

阅读 `./summary_basic_repro.md`，检查结论是否覆盖以下 3 个评价维度：

1. **数值复现合理**：JADE w/ archive 在 f1 上的最终 mean error 落在 `[1e-56, 1e-50]` 区间内（论文 Table IV 报告 `1.3e-54`）；在 f9 上的最终 mean error 落在 `[1e-6, 1e-3]` 区间内（论文报告 `1.4e-4` at gen 1000，0 at gen 5000）。如果落在 10× 之外仍可接受但要在 summary 中解释偏差来源。
2. **JADE 显著优于 DE/rand/1/bin**：在全部 4 个函数上，JADE w/ archive 的最终 mean error 比 DE/rand/1/bin 至少低 5 个数量级（参考论文 Table IV：f1 上 JADE=1.3e-54 vs DE=9.8e-14，差距 40 个数量级）。
3. **SR 数据合理**：JADE w/ archive 在 f1, f3, f9 的 SR 都应 ≥ 96%（论文报告 100%）；f5 受 Rosenbrock 在 D=30 难收敛影响，SR 落在 `[80, 100]%` 都算合理。
