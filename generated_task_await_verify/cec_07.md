[Agents]

复现 RCMAES 算法（./material），配置 python 环境。

研究 RCMAES 的维度依赖性：核心超参 r = 1.7 - 0.01·D 随 D 变化（D=10 时 r=1.6，D=30 时 r=1.4，D=50 时 r=1.2，D=100 时 r=0.7）。论文 §III 指出 D ≤ 70 时 r ≥ 1（快于线性缩减），D > 70 时 r < 1（慢于线性）。

至少对比以下 3 种 r 选择策略，在 **CEC2017** 的 D ∈ {10, 30, 50, 100} 四个维度上跑（budget = D × 10000 evals）：

1. `paper_dim_dependent`：r = 1.7 - 0.01·D（论文默认，随 D 自适应）
2. `fixed_linear`：r = 1.0（固定线性，所有 D 都一样）
3. `fixed_aggressive`：r = 1.5（固定快于线性，所有 D 都一样）

每个 (D, r 策略) 组合在 CEC2017 全部 29 个函数上跑 15 次（高 D 下 51 次太慢，15 次足够看趋势）。

记录每个 D 下的 overall E、r 对 D 的最优值（基于实验数据反推）、与 paper 的差距。

把结论写到 `./summary_dim_scaling.md`。

---

[Judge (IQ requirement: low-IQ)]

Look at `./summary_dim_scaling.md`, check whether conclusion cover the following points:

1. 在 D=10/30/50（r > 1 区域），paper_dim_dependent 的 overall E 都优于或等于 fixed_linear
2. 在 D=100（r=0.7 区域），fixed_aggressive（r=1.5）明显劣于 paper_dim_dependent（E 差距 ≥ 20%），证明高维下需要更慢的缩减
3. fixed_linear 在 D=100 上略优于 paper（差距 ≤ 5%），但在 D=10/30 上明显差于 paper（差距 ≥ 10%）
4. 实验数据反推的最优 r 随 D 单调下降，且与 paper 公式 r = 1.7 - 0.01·D 在 ±0.2 内一致
