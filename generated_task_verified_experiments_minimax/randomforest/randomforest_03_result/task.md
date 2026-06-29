[Agents]

读给定材料，做实验，写结论。

考察树的数量（n_estimators）对误差稳定/收敛的影响。数据：load_digits，70/30 划分（固定种子）。对 n_estimators ∈ {10, 50, 100, 200, 500, 1000} 分别训练 RandomForestClassifier（oob_score=True, random_state=0），记录 OOB 误差与留出测试误差。把「OOB/测试误差 随 n_estimators 的变化」写到 ./summary_n_trees.md。固定设置：数据集、划分、随机种子；唯一自变量为 n_estimators。

---

[Judge]

Look at `./summary_n_trees.md`, check whether conclusion cover the following points

1. 误差随 n_estimators 增加而下降并趋于平台（收敛）。
2. 误差不随树数增加而回升（加树不过拟合）。
3. 预测方差随树数增加而下降（更稳定）。


[Judge V2]

查阅 `./summary_n_trees.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；n_estimators∈{10…1000}、OOB+测试误差）：

1. 须给误差随 n_estimators 下降并平台（golden：OOB 0.132→0.040→0.029→0.024→0.0239→0.0231（10→1000）、200 后平台；可接受：单调降后平台）。（细化原 [Judge] 第 1 点）
2. 须给误差不随树数回升（不过拟合）（golden：OOB/测试均不回升；可接受：无回升）。（细化原 [Judge] 第 2 点）
3. 须给预测方差随树数降（更稳定）（golden：200 后稳定、OOB 与测试吻合；注 n=10 OOB 偏高因袋外样本缺失；可接受：方差降后稳定 + 点明少树 OOB 不可靠）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
