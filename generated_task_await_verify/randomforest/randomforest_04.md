[Agents]

读给定材料，做实验，写结论。

考察每次分裂的随机特征子采样数（max_features / mtry）对准确率与树之间相关性的影响。数据：load_digits（p=64 特征），70/30 划分（固定种子）。对 max_features ∈ {1, 'sqrt'(≈8), p/3(≈21), None(全部 p)} 分别训练 RandomForestClassifier（n_estimators=200, oob_score=True, random_state=0），记录 OOB 误差/测试准确率。把「准确率/OOB 误差 随 max_features 的变化」写到 ./summary_max_features.md。固定设置：数据集、n_estimators、划分、随机种子；唯一自变量为 max_features。

---

[Judge]

Look at `./summary_max_features.md`, check whether conclusion cover the following points

1. 用全部特征（max_features=p）时树更相关，准确率往往不最优。
2. 中等 mtry（如 'sqrt'）去相关效果最好，准确率最高/平台。
3. 极端 mtry=1 偏差过大，准确率下降。
