[Agents]

读给定材料，做实验，写结论。

考察 **特征相关性** 对 Isolation Forest 检测的影响：独立同分布特征 vs 多重共线特征下，检测质量（AUC）与正常/异常分布的分离度如何变化。Liu et al. 2008 §3.1 假设"独立属性上的随机分割"——特征相关时该假设被破坏，应观察到性能下降。

固定实验设置（不要更改）：
- 数据：两组二分类合成数据（已知正常/异常标签）：
  - **Set A（独立）**：`make_classification(n_samples=5000, n_features=20, n_informative=10, n_redundant=0, n_repeated=0, class_sep=1.0, weights=[0.98, 0.02], random_state=42)`；
  - **Set B（共线）**：在 Set A 基础上构造 10 个**与已有特征高相关**的额外特征——`X_extra = X[:, :10] + 0.05 * rng.randn(n, 10)`，再把这 20 维拼到原 20 维构成 30 维数据。
- 模型：sklearn.ensemble.IsolationForest（n_estimators=100, max_samples=256, contamination='auto', random_state=0），对两组数据各跑 **≥ 10 个不同 `random_state`**。
- 指标：每个种子用 `decision_function` 取异常分，对真实标签算 **ROC-AUC**；再统计正常 / 异常的 mean 异常分（与 _03 一致）。
- **仅 CPU**；整轮 **< 15 分钟**。

需要记录/报告的指标：
- 一张表：Set A（独立）vs Set B（共线）的 **ROC-AUC 均值 ± 标准差**（≥ 10 种子），以及正常 / 异常 mean 异常分差 `μ_norm - μ_anom`（越大越易分离）。
- 短结论：**Set B（共线）下 AUC 是否显著下降**（如下降 ≥ 0.03 即视为"特征相关对 iForest 构成明显挑战"）；并指出是否在共线数据上**异常分数的方差明显变大**（即检测置信度变差）。

把以上写到 `./summary_iforest_06_feature_correlation.md`。

---

[Judge]

Look at `./summary_iforest_06_feature_correlation.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 **Set A (独立) vs Set B (共线)** 在 ≥ 10 随机种子下的 ROC-AUC 均值 ± 标准差，以及"正常均值异常分 − 异常均值异常分"的差值，以表格呈现。
2. Set B（共线）的 ROC-AUC 显著低于 Set A（独立），**降幅 ≥ 0.03**（即共线性对 iForest 构成可测挑战）。
3. 短结论明确说明**共线场景下异常分分布的方差是否变大**（如 Set B 异常分的 std 较 Set A 大 ≥ 20%），并简要归因（"共线特征使 iTree 的随机分割在多个相关维度上重复做同样的事、降低有效特征多样性"）。
