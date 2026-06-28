[Agents]

读给定材料，做实验，写结论。

考察树的数量（n_estimators）对分数稳定性与检测质量的影响。同上数据（固定种子），对 n_estimators ∈ {10, 50, 100, 200, 500} 分别训练 IsolationForest（ψ=256）；为衡量稳定性，对每个 n_estimators 用多个 random_state 复跑，记录每个点异常分在复跑间的方差（取平均），并记录检测 AUC。把「分数方差、AUC 随 n_estimators 的变化」写到 ./summary_n_estimators.md。固定设置：数据集、ψ、复跑种子集合；唯一自变量为 n_estimators。

---

[Judge]

Look at `./summary_n_estimators.md`, check whether conclusion cover the following points

1. 随 n_estimators 增大，分数方差下降（更稳定）。
2. AUC 略升后趋于平台。
3. 超过约 100 棵树后提升边际递减。


[Judge V2]

查阅 `./summary_n_estimators.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；N=3000/d=8/10% 异常/ψ=256/20 复跑）：

1. 须给分数方差随 n_est 下降（golden：n_est=10/50/100/200/500 方差 8.44e-4/1.64e-4/8.03e-5/4.12e-5/1.45e-5；可接受：单调降）。（细化原 [Judge] 第 1 点）
2. 须给 AUC 略升后平台（golden：AUC 0.9927→0.9964→0.9966→0.9967→0.9966；可接受：略升后平台 ≥0.996）。（细化原 [Judge] 第 2 点）
3. 须给 >100 棵边际递减（golden：100→500 方差 8.03e-5→1.45e-5、AUC 平台；可接受：>100 后 AUC 增量 <0.001）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
