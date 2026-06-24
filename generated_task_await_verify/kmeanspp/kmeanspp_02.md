[Agents]

读给定材料，做实验，写结论。

考察 k-means++ 选种相对均匀随机选种的最终代价（inertia）优势。用 sklearn.datasets.make_blobs 生成若干高斯簇（n=5000 点，k=10 簇，固定随机种子）。对 sklearn.cluster.KMeans（init='k-means++', n_init=1）与（init='random', n_init=1）各跑约 30 个不同 random_state；记录每次的最终 inertia。比较两种选种的 inertia 均值、标准差、最差值。把「k-means++ vs random 的 inertia 分布对比」写到 ./summary_cost_vs_random.md。固定设置：数据集、k、n_init=1、random_state 集合；自变量为选种方式。

---

[Judge]

Look at `./summary_cost_vs_random.md`, check whether conclusion cover the following points

1. k-means++ 的平均 inertia 不高于（通常低于）均匀随机。
2. k-means++ 的 inertia 方差显著更小（更稳定）。
3. k-means++ 避免了灾难性的高 inertia 局部最优（最差值更小）。
