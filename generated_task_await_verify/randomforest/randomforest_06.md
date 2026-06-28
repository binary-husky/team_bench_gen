[Agents]

读给定材料，做实验，写结论。

考察**类别不平衡 + class_weight**对随机森林的 OOB / 测试误差及 ROC-AUC 的影响——验证 Breiman 论文是否在加权方案下仍能取得 OOB ≈ 测试误差，并衡量 `class_weight='balanced'` vs 默认（无权重）的差距。

固定实验设置（不要更改）：
- 数据：构造一个人工不平衡二分类数据集——用 sklearn.datasets.make_classification 生成 n=2000、n_features=20、n_informative=10、weights=[0.9, 0.1]（少数类占 10%）、class_sep=1.0、random_state=42。
- 划分：70/30 训练/测试（固定 random_state=0），保留训练集的类分布。
- 模型：sklearn.ensemble.RandomForestClassifier
  - n_estimators=200, max_features='sqrt', n_jobs=1
  - 两个变体：`(a) class_weight=None` (默认)、`(b) class_weight='balanced'`；
  - 每个变体打开 `oob_score=True`。
- 每个变体用 **≥ 10 个不同 `random_state`** 独立重复，记录每次的 OOB 准确率、测试准确率、测试 macro-F1、测试 ROC-AUC。
- **仅 CPU**；整轮 **< 30 分钟**。

需要记录/报告的指标：
- 一张表：两个变体（`balanced` vs `None`）的**均值 ± 标准差**（≥ 10 种子）四列：OOB accuracy、test accuracy、test macro-F1、test ROC-AUC。
- 一张图：测试 ROC 曲线（用 `predict_proba` 算）跨 10 种子的均值曲线（`np.mean(...)` 后再画）对比两个变体。
- 短结论：**class_weight='balanced' 对 macro-F1 与 ROC-AUC 提升多少**（一般 +5pp–+20pp macro-F1、+0.05–+0.20 ROC-AUC）；**OOB 与测试准确率差距在加权变体下是否仍然 < 3pp**（即加权不破坏 OOB ≈ 测试的对应关系）。

把以上写到 `./summary_rf_06_class_imbalance.md`。

---

[Judge]

Look at `./summary_rf_06_class_imbalance.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 `class_weight=None` vs `class_weight='balanced'` 两个变体在 ≥ 10 个随机种子下的 OOB accuracy、test accuracy、test macro-F1、test ROC-AUC 四列**均值 ± 标准差**，以表格呈现。
2. `class_weight='balanced'` 变体的**test macro-F1 与 ROC-AUC 显著高于**无权重变体（macro-F1 提升 ≥ 3pp，ROC-AUC 提升 ≥ 0.03），并给出具体数值。
3. 两个变体的 **OOB accuracy 与 test accuracy 差距均 < 5pp**（验证加权不破坏 OOB ≈ 测试对应关系）；并以 1 张 ROC 曲线图（跨种子均值）作为可视化证据。
