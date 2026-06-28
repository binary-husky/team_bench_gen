[Agents]

读给定材料，做实验，写结论。

考察 t-SNE 收敛所需的迭代数。数据：sklearn.datasets.load_digits。对 max_iter ∈ {250, 500, 1000, 2000} 逐一运行 sklearn.manifold.TSNE（n_components=2, init='pca', perplexity=30, learning_rate='auto', random_state=0），每次记录两个指标：(a) 最终 KL 散度（取 TSNE 拟合后对象的 .kl_divergence_ 属性）；(b) 二维嵌入按数字标签的 silhouette score。把迭代数与两个指标的对照、以及“约多少步基本收敛”的结论写到 ./summary_iterations.md。固定设置：上述超参数；仅 max_iter 为自变量。

---

[Judge]

Look at `./summary_iterations.md`, check whether conclusion cover the following points

1. KL 散度随 max_iter 增加而下降，并在约 1000 步附近趋于平台（已收敛）。
2. 迭代过少（如 250）时嵌入质量（silhouette）明显更差。
3. 超过约 1000–2000 步后指标提升已很小（边际收益递减）。
