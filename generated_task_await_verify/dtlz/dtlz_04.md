[Agents]

读给定材料，做实验，写结论。

研究 **DTLZ2 在目标维数 M ∈ {3, 5, 8, 10, 15} 上的扩展性**——固定问题（DTLZ2 单位球面前沿是最适合 many-objective 测试的，因为前沿几何对所有 M 都明确定义为第一象限单位球面），扫描 M，对比 NSGA-II、NSGA-III、MOEA/D 三个经典 MOEA 在 many-objective regime 下的退化模式。

固定实验设置：

- 测试问题：DTLZ2，决策变量数 n = M + k − 1，固定 k = 10
- 算法对比（3 个）：
    1. **NSGA-II**（二元锦标赛 + 拥挤距离）
    2. **NSGA-III**（参考点引导，使用 Das-Dennis reference directions，每个 M 用 (p=12, M=3), (p=10, M=5), (p=8, M=8), (p=6, M=10), (p=4, M=15) 等近似保持参考点数 ~100）
    3. **MOEA/D**（Tchebycheff 分解，邻居大小 T=20）
- 种群大小：N = 100（NSGA-III 参考点数与 N 一致或略低）
- 交叉：SBX（η_c = 20, p_c = 0.9）
- 变异：多项式变异（η_m = 20, p_m = 1/n）
- 终止条件：500 代
- 独立运行次数：每个 (M, algorithm) 组合 21 次
- 总计算量：5 个 M × 3 个算法 × 21 次 = 315 runs

需要计算的指标：

1. **IGD**（参考集：每个 M 在单位球面第一象限均匀采 5000 个点）
2. **HV**（参考点 (1.1, 1.1, ..., 1.1)，注意 HV 在高维下计算代价大，可用 WFG 或 Monte Carlo 近似）
3. **非支配比例**：最终种群中处于第一非支配层的比例（many-objective 下，NSGA-II 的非支配排序会失效——几乎所有解都在第一层，选择压力消失）
4. **决策变量收敛**：g(x_M) 的最终值

把以下分析写到 `./summary_dtlz_04_many_objective.md`：

1. 5 M × 3 算法的 IGD/HV/g 表（mean ± std）
2. **NSGA-II 退化曲线**：IGD 随 M 的变化，识别"灾难性退化"的临界 M（论文 §6.6 提到 "a large proportion of a random initial population to be non-dominated to each other" 在高维下出现，导致选择压力消失）
3. **NSGA-III 的相对优势**：在 M ≥ 8 的 many-objective regime 下，NSGA-III 的 IGD 应该明显优于 NSGA-II（这是 NSGA-III 论文 Deb-Jain 2014 的核心 claim）
4. **MOEA/D 的位置**：MOEA/D 在中间 M（5-8）上应与 NSGA-III 相当，但在 M ≥ 10 时也会因权重向量分布不足而退化
5. **非支配比例诊断**：在 M=15 下，NSGA-II 的非支配比例应接近 100%（论文 §6.6 的"selection pressure disappears"），而 NSGA-III 通过 reference-direction 的 niche 仍能维持选择压力

---

[Judge]

阅读 `./summary_dtlz_04_many_objective.md`，检查结论是否覆盖以下 3 个评价维度：

1. **NSGA-II 在 M ≥ 8 上灾难性退化**：NSGA-II 的 IGD 在 M=8 比 M=3 高至少 5 倍；在 M=15 比 M=3 高至少 20 倍。同时非支配比例在 M=15 接近 100%（≥ 95%），直接验证论文 §6.6 的"selection pressure disappears"——选择压力在高维下消失，导致 NSGA-II 的非支配排序退化为随机选择。Summary 必须报告每个 M 的非支配比例。
2. **NSGA-III 在 many-objective 上保持优势**：在 M ∈ {8, 10, 15} 上，NSGA-III 的 IGD 比 NSGA-II 低至少 50%（半一下）；在 M ∈ {3, 5} 上 NSGA-III 与 NSGA-II 差距 ≤ 20%（低维下两者接近）。这验证 NSGA-III 论文（Deb-Jain 2014 IEEE TEVC）的核心 claim。
3. **MOEA/D 与 NSGA-III 在中间 M 上相当**：在 M=5 上 MOEA/D 与 NSGA-III 的 IGD 差距 ≤ 30%（参考点引导 vs 分解两类方法在中维下表现接近）；但在 M ≥ 10 上 MOEA/D 退化更明显（IGD 比 NSGA-III 高 ≥ 50%），因为权重向量在球面第一象限的分布密度下降。Summary 必须明确指出三个算法各自最适合的 M 区间。
