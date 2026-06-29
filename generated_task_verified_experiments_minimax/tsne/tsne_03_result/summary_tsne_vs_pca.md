# PCA vs. t-SNE 二维降维质量比较 — sklearn `load_digits`

## 1. 实验设定

- **数据**：`sklearn.datasets.load_digits`，1797 × 64，10 个数字类别。
- **自变量**：降维方法（PCA vs. t-SNE）。
- **被比较的二维嵌入**：
  - **PCA**：`PCA(n_components=2, random_state=0)`，直接取前 2 个主成分。
  - **t-SNE**：`TSNE(n_components=2, init='pca', perplexity=30, learning_rate='auto', max_iter=1000, random_state=0)`（与任务指定完全一致）。
- **固定超参数**：以上即所有超参数；`random_state=0` 保证可复现。
- **评价指标**：
  1. **Silhouette score**（按数字标签，metric=Euclidean）— 度量聚类可分性。
  2. **Trustworthiness**（`n_neighbors=12`）— 度量 12-近邻在 64-D 原始空间与 2-D 嵌入空间之间被保留的比例，反映局部邻域保持。
- 脚本：`run_experiment.py`；原始结果：`results.json`；2-D 坐标：`X_pca.npy`, `X_tsne.npy`, `y.npy`。

## 2. 原始结果

| 方法 | Silhouette ↑ | Trustworthiness @ k=12 ↑ | 拟合用时 (s) | 备注 |
|---|---:|---:|---:|---|
| **PCA** (2 维) | **0.1051** | **0.8296** | 0.002 | 累计方差解释率 = 28.51%（PC1=14.89%, PC2=13.62%） |
| **t-SNE** | **0.5557** | **0.9917** | 1.84 | n_iter=999，KL 散度 = 0.7536 |
| Δ(t-SNE − PCA) | **+0.4507** | **+0.1621** | +1.84 | t-SNE 在两项指标上均大幅领先 |

两个指标的取值范围均为 [-1, 1]（silhouette）和 [0, 1]（trustworthiness），数值越高越好。

## 3. 指标解读

### 3.1 聚类可分性（Silhouette，按数字标签）

- **PCA = 0.105**：接近 0，说明前 2 个主成分形成的 2-D 投影里，10 个数字类别之间几乎没有清晰间隔；10 个数字簇大量重叠，这与 PCA 仅捕获 ~28.5% 方差（每个 PC 仅 14–15%）一致 — 两个线性方向远不足以分离 64 维中的非线性流形结构。
- **t-SNE = 0.556**：远高于 PCA，说明 10 个数字类别在 2-D 流形上形成了彼此清楚分开的团。差值 Δ = +0.45 是非常显著的提升。
- **机理**：t-SNE 在低维空间用 **Student-t（重尾）** 分布来建模相似度，重的尾部让中度不相似点之间的“吸引力”快速衰减、而“排斥力”相对增强，从而把不同类别彼此推开（van der Maaten & Hinton, 2008, §3.2–3.3）。这正是 silhouette 所度量的。

### 3.2 局部近邻保持（Trustworthiness @ k=12）

- **PCA = 0.830**：合理水平，64→2 的线性投影里大部分 12-近邻仍被保留（这与 PCA 在高维局部近似各向同性的几何有关）。
- **t-SNE = 0.992**：几乎完美。12-近邻里 99% 以上都被 2-D 嵌入正确保留。
- **机理**：t-SNE 在高维空间用 **Gaussian + 固定 perplexity** 直接构造局部近邻概率（P 分布），并在低维空间最小化 KL 散度以匹配该分布 — 优化目标本身就以“局部近邻保持”为核心（van der Maaten & Hinton, 2008, §2, §3.1）。trustworthiness 正是度量这件事的指标，t-SNE 接近上限是预期。

## 4. 结论

> **在 `load_digits`（1797 × 64，10 类）上，使用任务指定的固定超参数，t-SNE 在『簇分离』和『局部近邻保持』两方面都明显优于 PCA。**

具体而言：

1. **哪种方法更利于簇分离？** — **t-SNE**。
   - Silhouette：0.5557 vs. 0.1051（PCA 的 5 倍以上）。
   - 直观原因：t-SNE 用重尾 Student-t 分布抑制了 SNE 的“拥挤问题”，能把 10 个非线性流形从 64-D 投影到 2-D 后彼此清楚地拉开（van der Maaten & Hinton, 2008, §3.3）。PCA 受限于线性假设，2 个主成分只解释了 ~28.5% 的方差，多个数字类别在 2-D 投影里严重重叠。

2. **哪种方法更利于局部近邻保持？** — **t-SNE**。
   - Trustworthiness (k=12)：0.9917 vs. 0.8296。
   - 直观原因：t-SNE 的代价函数 KL(P‖Q) 显式最小化高–低维局部近邻分布的差异，perplexity 30 正好控制局部尺度；而 PCA 只能保留全局方差方向，2-D 投影必然把部分近邻推开。

3. **何时仍可能选 PCA？**
   - **速度/可解释性**：PCA 仅 0.002 s，且每个主成分是原始特征的线性组合，方向有明确含义；t-SNE 是随机优化、不可线性回投。
   - **全局结构**：t-SNE 以牺牲全局结构换局部结构（van der Maaten & Hinton, 2008, §6.2 弱点 2）。本任务不评估全局结构，故 t-SNE 的这项缺点未在指标中暴露；如果关心类别间的“相对距离”，PCA 反而更稳定。
   - **小预算 + 大数据**：n=1797 时 t-SNE 仅 1.8 s，可接受；n≥10⁴ 时 t-SNE 的 O(n²) 复杂度会迅速成为瓶颈。

## 5. 一句话总结

> 在相同的 64-D 数字数据上，**t-SNE（perplexity=30, init=pca, 1000 iter, random_state=0）以约 0.45 的 silhouette 优势与约 0.16 的 trustworthiness 优势全面胜过 PCA(2)**，证实了它对『簇分离』和『局部近邻保持』两个目标都更有效；其代价是更高的计算成本与失去全局距离含义。

## 参考

- van der Maaten, L., & Hinton, G. (2008). *Visualizing Data using t-SNE.* Journal of Machine Learning Research, 9, 2579–2605. （已附在 `tsne_material/`）
- scikit-learn：`sklearn.decomposition.PCA`，`sklearn.manifold.TSNE`，`sklearn.metrics.silhouette_score`，`sklearn.manifold.trustworthiness`。
