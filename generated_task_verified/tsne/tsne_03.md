[Agents]

读给定材料，做实验，写结论。

在同一份小数据上比较 t-SNE 与 PCA 的二维降维质量。数据：sklearn.datasets.load_digits（1797×64，10 类）。分别计算两种二维嵌入：(1) PCA 取前 2 个主成分；(2) sklearn.manifold.TSNE（n_components=2, init='pca', perplexity=30, learning_rate='auto', max_iter=1000, random_state=0）。对两种二维嵌入分别计算：按数字标签的 silhouette score，以及 trustworthiness（n_neighbors=12）。把对照结果与“哪种方法更利于簇分离 / 局部近邻保持”的结论写到 ./summary_tsne_vs_pca.md。固定设置：上述超参数；降维方法（PCA vs t-SNE）为自变量。

---

[Judge]

Look at `./summary_tsne_vs_pca.md`, check whether conclusion cover the following points

1. t-SNE 的二维嵌入在簇分离（silhouette）上显著优于 PCA。
2. t-SNE 在局部近邻保持（trustworthiness）上也优于（或不劣于）PCA。
3. 结论指出 PCA 只能保留线性全局方差、难以分离非线性簇结构，而 t-SNE 更擅长暴露簇结构。


[Judge V2]

查阅 `./summary_tsne_vs_pca.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；digits、t-SNE perplexity=30 vs PCA、sklearn 1.9.0）：

1. 须给 t-SNE 簇分离 silhouette 显著优于 PCA（golden：t-SNE 0.5557 vs PCA 0.1051（+0.4507）；可接受：t-SNE >PCA by ≥0.2）。（细化原 [Judge] 第 1 点）
2. 须给 t-SNE 局部近邻 trustworthiness(k=12) 优于 PCA（golden：t-SNE 0.9917 vs PCA 0.8296（+0.16）；可接受：t-SNE ≥PCA）。（细化原 [Judge] 第 2 点）
3. 须给 PCA 只保线性全局方差难分离非线性簇、t-SNE 更擅暴露簇结构（golden：PCA 前 2 主成分仅解释 28.51% 方差、t-SNE 非线性拉开；可接受：点明线性 vs 非线性）。注：t-SNE 不保全局几何/不可逆、PCA 线性可逆（可接受：点明前提）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
