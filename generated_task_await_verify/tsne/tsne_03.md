[Agents]

读给定材料，做实验，写结论。

在同一份小数据上比较 t-SNE 与 PCA 的二维降维质量。数据：sklearn.datasets.load_digits（1797×64，10 类）。分别计算两种二维嵌入：(1) PCA 取前 2 个主成分；(2) sklearn.manifold.TSNE（n_components=2, init='pca', perplexity=30, learning_rate='auto', max_iter=1000, random_state=0）。对两种二维嵌入分别计算：按数字标签的 silhouette score，以及 trustworthiness（n_neighbors=12）。把对照结果与“哪种方法更利于簇分离 / 局部近邻保持”的结论写到 ./summary_tsne_vs_pca.md。固定设置：上述超参数；降维方法（PCA vs t-SNE）为自变量。

---

[Judge]

Look at `./summary_tsne_vs_pca.md`, check whether conclusion cover the following points

1. t-SNE 的二维嵌入在簇分离（silhouette）上显著优于 PCA。
2. t-SNE 在局部近邻保持（trustworthiness）上也优于（或不劣于）PCA。
3. 结论指出 PCA 只能保留线性全局方差、难以分离非线性簇结构，而 t-SNE 更擅长暴露簇结构。
