[Agents]

读给定材料，做实验，写结论。

考察树的数量（n_estimators）对误差稳定/收敛的影响。数据：load_digits，70/30 划分（固定种子）。对 n_estimators ∈ {10, 50, 100, 200, 500, 1000} 分别训练 RandomForestClassifier（oob_score=True, random_state=0），记录 OOB 误差与留出测试误差。把「OOB/测试误差 随 n_estimators 的变化」写到 ./summary_n_trees.md。固定设置：数据集、划分、随机种子；唯一自变量为 n_estimators。

---

[Judge]

Look at `./summary_n_trees.md`, check whether conclusion cover the following points

1. 误差随 n_estimators 增加而下降并趋于平台（收敛）。
2. 误差不随树数增加而回升（加树不过拟合）。
3. 预测方差随树数增加而下降（更稳定）。
