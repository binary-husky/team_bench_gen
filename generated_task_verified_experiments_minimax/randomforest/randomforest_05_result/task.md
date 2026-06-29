[Agents]

读给定材料，做实验，写结论。

将随机森林与单棵决策树对比（方差削减 / 抗过拟合）。数据：load_digits，对若干随机种子分别做 70/30 划分。对每个种子分别训练：(a) sklearn.ensemble.RandomForestClassifier（n_estimators=200）；(b) sklearn.tree.DecisionTreeClassifier。记录各自的训练误差与测试误差。比较两者测试误差的均值与标准差（跨种子）。把「RF vs 单棵树 的测试误差均值/方差、训练误差对比」写到 ./summary_vs_single_tree.md。固定设置：数据集、n_estimators、划分、随机种子集合；自变量为模型类型。

---

[Judge]

Look at `./summary_vs_single_tree.md`, check whether conclusion cover the following points

1. RF 的测试误差低于单棵决策树。
2. RF 跨种子的测试误差方差显著更小（更稳定）。
3. 单棵树严重过拟合（训练误差≈0、测试误差高），RF 明显抗过拟合。


[Judge V2]

查阅 `./summary_vs_single_tree.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；RF(n_est=200) vs 单树、20 种子）：

1. 须给 RF 测试误差低于单树（golden：RF 0.0255 vs DT 0.1594（低 0.134 / 相对 84%）；可接受：RF<DT）。（细化原 [Judge] 第 1 点）
2. 须给 RF 跨种子测试误差方差显著更小（golden：RF std 0.0059 vs DT 0.0105（DT/RF 1.80×、方差减 68%）；可接受：RF std ≤0.7× DT）。（细化原 [Judge] 第 2 点）
3. 须给单树严重过拟合(训练≈0 测试高)、RF 抗过拟合（golden：训练均 0、RF 测试 0.0255 vs DT 0.1594、gap RF 0.0255≈DT 的 1/6；可接受：DT gap 大、RF 小）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
