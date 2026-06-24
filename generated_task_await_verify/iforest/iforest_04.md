[Agents]

读给定材料，做实验，写结论。

考察树的数量（n_estimators）对分数稳定性与检测质量的影响。同上数据（固定种子），对 n_estimators ∈ {10, 50, 100, 200, 500} 分别训练 IsolationForest（ψ=256）；为衡量稳定性，对每个 n_estimators 用多个 random_state 复跑，记录每个点异常分在复跑间的方差（取平均），并记录检测 AUC。把「分数方差、AUC 随 n_estimators 的变化」写到 ./summary_n_estimators.md。固定设置：数据集、ψ、复跑种子集合；唯一自变量为 n_estimators。

---

[Judge]

Look at `./summary_n_estimators.md`, check whether conclusion cover the following points

1. 随 n_estimators 增大，分数方差下降（更稳定）。
2. AUC 略升后趋于平台。
3. 超过约 100 棵树后提升边际递减。
