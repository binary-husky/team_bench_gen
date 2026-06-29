[Agents]

读给定材料，做实验，写结论。

考察每次分裂的随机特征子采样数（max_features / mtry）对准确率与树之间相关性的影响。数据：load_digits（p=64 特征），70/30 划分（固定种子）。对 max_features ∈ {1, 'sqrt'(≈8), p/3(≈21), None(全部 p)} 分别训练 RandomForestClassifier（n_estimators=200, oob_score=True, random_state=0），记录 OOB 误差/测试准确率。把「准确率/OOB 误差 随 max_features 的变化」写到 ./summary_max_features.md。固定设置：数据集、n_estimators、划分、随机种子；唯一自变量为 max_features。

---

[Judge]

Look at `./summary_max_features.md`, check whether conclusion cover the following points

1. 用全部特征（max_features=p）时树更相关，准确率往往不最优。
2. 中等 mtry（如 'sqrt'）去相关效果最好，准确率最高/平台。
3. 极端 mtry=1 偏差过大，准确率下降。


[Judge V2]

查阅 `./summary_max_features.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；max_features∈{1,sqrt,p/3,None}、digits）：

1. 须给全特征(mf=p)树更相关、准确率不最优（golden：None 准确率 0.9593/OOB 0.0565 最差、相关性 0.72 最高；可接受：None 非最优）。（细化原 [Judge] 第 1 点）
2. 须给中等 mtry('sqrt')去相关最好、准确率最高（golden：sqrt(=8) 准确率 0.9778/OOB 0.0270 最低；可接受：sqrt 最优）。（细化原 [Judge] 第 2 点）
3. 须给极端 mtry=1 偏差大、准确率降（golden：mf=1 准确率 0.9611/OOB 0.0366、相关性 0.41 最低但单树弱；可接受：mf=1 非最优）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
