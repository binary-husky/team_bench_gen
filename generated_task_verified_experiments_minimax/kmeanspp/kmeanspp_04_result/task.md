[Agents]

读给定材料，做实验，写结论。

考察收敛所需 Lloyd 迭代数。同上数据（n=5000, k=10，固定种子），对 init='k-means++' 与 init='random'（均 n_init=1）各跑约 30 个 random_state，记录每次 KMeans 收敛的迭代数（.n_iter_）。比较两种选种的平均迭代数、标准差与最差值。把「收敛迭代数 k-means++ vs random」写到 ./summary_lloyd_iters.md。固定设置：数据集、k、n_init=1、random_state 集合、收敛容差；自变量为选种方式。

---

[Judge]

Look at `./summary_lloyd_iters.md`, check whether conclusion cover the following points

1. k-means++ 平均需要更少的 Lloyd 迭代即收敛。
2. 迭代数方差更低。
3. 灾难性的慢收敛情形更少。


[Judge V2]

查阅 `./summary_lloyd_iters.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；make_blobs n=5000/k=10/d=10、30 种子、n_init=1）：

1. 须给 km++ 平均迭代更少（golden：km++ 4.27 vs random 15.27；可接受：km++ < random）。（细化原 [Judge] 第 1 点）
2. 须给迭代数方差更低（golden：km++ std 4.48 vs random 4.88（边际更低，主增益在均值）；可接受：km++ std ≤ random）。（细化原 [Judge] 第 2 点——方差优势边际，主增益在均值）
3. 须给灾难性慢收敛更少（golden：km++ 均值 4.27 远低于 random 15.27、最差情形更少；可接受：km++ 最差迭代 < random 最差）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
