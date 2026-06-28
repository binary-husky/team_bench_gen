[Agents]

读给定材料，做实验，写结论。

将随机森林与单棵决策树对比（方差削减 / 抗过拟合）。数据：load_digits，对若干随机种子分别做 70/30 划分。对每个种子分别训练：(a) sklearn.ensemble.RandomForestClassifier（n_estimators=200）；(b) sklearn.tree.DecisionTreeClassifier。记录各自的训练误差与测试误差。比较两者测试误差的均值与标准差（跨种子）。把「RF vs 单棵树 的测试误差均值/方差、训练误差对比」写到 ./summary_vs_single_tree.md。固定设置：数据集、n_estimators、划分、随机种子集合；自变量为模型类型。

---

[Judge]

Look at `./summary_vs_single_tree.md`, check whether conclusion cover the following points

1. RF 的测试误差低于单棵决策树。
2. RF 跨种子的测试误差方差显著更小（更稳定）。
3. 单棵树严重过拟合（训练误差≈0、测试误差高），RF 明显抗过拟合。
