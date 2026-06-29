[Agents]

读给定材料，做实验，写结论。

考察 k-means++ 选种相对均匀随机选种的最终代价（inertia）优势。用 sklearn.datasets.make_blobs 生成若干高斯簇（n=5000 点，k=10 簇，固定随机种子）。对 sklearn.cluster.KMeans（init='k-means++', n_init=1）与（init='random', n_init=1）各跑约 30 个不同 random_state；记录每次的最终 inertia。比较两种选种的 inertia 均值、标准差、最差值。把「k-means++ vs random 的 inertia 分布对比」写到 ./summary_cost_vs_random.md。固定设置：数据集、k、n_init=1、random_state 集合；自变量为选种方式。

---

[Judge]

Look at `./summary_cost_vs_random.md`, check whether conclusion cover the following points

1. k-means++ 的平均 inertia 不高于（通常低于）均匀随机。
2. k-means++ 的 inertia 方差显著更小（更稳定）。
3. k-means++ 避免了灾难性的高 inertia 局部最优（最差值更小）。


[Judge V2]

查阅 `./summary_cost_vs_random.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；make_blobs n=5000/k=10、30 种子、n_init=1）：

1. 须给 km++ 平均 inertia ≤ random（golden：km++ 9620.12 vs random 10690.76（低 10.0%）；可接受：km++ 均值 ≤ random）。（细化原 [Judge] 第 1 点）
2. 须给 km++ 方差显著更小（golden：km++ std 820.89 vs random 1475.79（约 56%）；可接受：km++ std ≤0.7× random）。（细化原 [Judge] 第 2 点）
3. 须给 km++ 避免灾难性高 inertia（golden：km++ max 10624.01 vs random max 15219.08（高 43%）；可接受：km++ max < random max）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
