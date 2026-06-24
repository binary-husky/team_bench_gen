[Agents]

读给定材料，做实验，写结论。

将 IsolationForest 与基线方法对比。同上数据（固定种子）。分别用 sklearn.ensemble.IsolationForest（ψ=256, n_estimators=100, random_state=0）与 sklearn.neighbors.LocalOutlierFactor（基线）做异常检测，记录各自的检测 AUC（roc_auc_score）与训练/预测耗时。把「iForest vs LOF 的 AUC 与耗时对比」写到 ./summary_vs_baseline.md。固定设置：数据集、各方法参数、random_state；自变量为检测方法。

---

[Judge]

Look at `./summary_vs_baseline.md`, check whether conclusion cover the following points

1. iForest 的 AUC 与 LOF 相当或更高。
2. iForest 训练/预测更快（复杂度更低、扩展性更好）。
3. iForest 无需距离/密度计算（基于随机隔离），与 LOF 的密度估计形成对比。
