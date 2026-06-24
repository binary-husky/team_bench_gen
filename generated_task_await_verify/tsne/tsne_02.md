[Agents]

读给定材料，做实验，写结论。

复现并考察困惑度（perplexity）对 t-SNE 二维嵌入的影响。使用 sklearn.datasets.load_digits（共 1797 个样本、64 维、10 类）作为小规模数据；对 perplexity ∈ {5, 15, 30, 50, 100, 200} 逐一运行 sklearn.manifold.TSNE（n_components=2, init='pca', learning_rate='auto', max_iter=1000, random_state=0，其余默认）。每次运行后记录两个指标：(a) 二维嵌入按数字标签的 silhouette score（sklearn.metrics.silhouette_score）；(b) trustworthiness（sklearn.manifold.trustworthiness, n_neighbors=12）。把 perplexity 与两个指标的对照表、以及哪个 perplexity 最优的结论写到 ./summary_perplexity.md。固定设置：上述所有超参数；仅 perplexity 为自变量。

---

[Judge]

Look at `./summary_perplexity.md`, check whether conclusion cover the following points

1. perplexity 过小（如 5）时嵌入明显变差（silhouette 偏低、簇碎裂）。
2. 中等 perplexity（约 30 附近）取得最佳簇分离（silhouette 最高）。
3. perplexity 过大（如 200，相对 1797 个样本已偏大）时全局结构被压扁、silhouette 再次下降。
