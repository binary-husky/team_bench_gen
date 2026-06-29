[Agents]

读给定材料，做实验，写结论。

将 IsolationForest 与基线方法对比。同上数据（固定种子）。分别用 sklearn.ensemble.IsolationForest（ψ=256, n_estimators=100, random_state=0）与 sklearn.neighbors.LocalOutlierFactor（基线）做异常检测，记录各自的检测 AUC（roc_auc_score）与训练/预测耗时。把「iForest vs LOF 的 AUC 与耗时对比」写到 ./summary_vs_baseline.md。固定设置：数据集、各方法参数、random_state；自变量为检测方法。

---

[Judge]

Look at `./summary_vs_baseline.md`, check whether conclusion cover the following points

1. iForest 的 AUC 与 LOF 相当或更高。
2. iForest 训练/预测更快（复杂度更低、扩展性更好）。
3. iForest 无需距离/密度计算（基于随机隔离），与 LOF 的密度估计形成对比。


[Judge V2]

查阅 `./summary_vs_baseline.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；散布式稀疏异常、iForest ψ=256/n_est=100 vs LOF、5 次重复）：

1. 须给 iForest AUC 与 LOF 相当或更高（golden：iForest 0.9978 vs LOF 0.9968、+0.0010；可接受：iForest AUC ≥ LOF−0.005）。（细化原 [Judge] 第 1 点）
2. 须给 iForest 更快/扩展性更好（golden：iForest 491ms vs LOF 4471ms、9.1×；可接受：iForest ≤ LOF/2）。（细化原 [Judge] 第 2 点）
3. 须给 iForest 无需距离/密度（基于随机隔离），与 LOF 密度估计对比（可接受：点明此差异）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
