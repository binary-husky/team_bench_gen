[Agents]

读给定材料，做实验，写结论。

考察正常点与异常点的异常分（及路径长度）分布差异。同上生成数据（正常簇 + ~2% 注入离群，固定种子），训练 IsolationForest（ψ=256, n_estimators=100, random_state=0）。记录每个点的异常分（可用 IsolationForest 的 decision_function，或按论文由平均路径长度换算 s = 2^{-E[h]/c(ψ)}），分别统计正常点与异常点的分布（均值/中位数/分位），并以真实标签计算 AUC 衡量可分性。把「正常 vs 异常 的异常分分布对比、可分性」写到 ./summary_score_distribution.md。固定设置：数据集、ψ、n_estimators、random_state；本题为分布测量（无自变量）。

---

[Judge]

Look at `./summary_score_distribution.md`, check whether conclusion cover the following points

1. 异常点被赋予显著更强的异常性（路径更短 / 论文异常分 s 更高 / decision_function 更负）。
2. 两类异常分分布大体可分。
3. AUC 较高（异常分能将异常排在正常之上）。


[Judge V2]

查阅 `./summary_score_distribution.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；2040 点、d=5、~2% 远端离群、ψ=256、n_est=100）：

1. 须给异常点异常性更强（路径更短/s 更高/decision_function 更负）（golden：异常 s 均值 0.775 vs 正常 0.420、正常 95 分位 0.499 < 异常 min 0.750；可接受：异常 s 均值 > 正常 +0.2）。（细化原 [Judge] 第 1 点）
2. 须给两类分布大体可分（golden：空带 ~0.13、几乎不重叠（正常 max 0.619 < 异常 min 0.750）；可接受：分布分离、重叠小）。（细化原 [Judge] 第 2 点）
3. 须给 AUC 较高（异常排在正常之上）（golden：分布无重叠 ⇒ AUC≈1.0；可接受：AUC ≥0.95）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
