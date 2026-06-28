[Agents]

读给定材料，做实验，写结论。

考察 **n_init 多次随机重启**对**均匀随机选种**的修复能力——即"均匀随机选种 + n_init=N 次重启，取最佳"是否能追上 k-means++ 单次（n_init=1）的代价。

固定实验设置（不要更改）：
- 数据：sklearn.datasets.make_blobs 生成 n=5000 样本、k=10 个**良好分离**的高斯簇（cluster_std=0.5，固定 random_state=42），与 `_02` 保持一致以利对比。
- 算法：sklearn.cluster.KMeans（n_init=N, init='random'）以及 KMeans（n_init=1, init='k-means++'）。
- 网格：
  - `n_init ∈ {1, 2, 5, 10, 20, 50, 100}` 对应 `init='random'`；
  - `init='k-means++'` 仅 `n_init=1`（单次）作为对照基准。
- 每个配置用 **≥ 30 个不同 `random_state`** 独立重复，记录每次的最终 inertia。
- **仅 CPU**；整轮 **< 30 分钟**。

需要记录/报告的指标：
- 一张表 / 图：`init='random'` 各 n_init 下的 inertia 跨种子均值 ± 标准差，以及 `init='k-means++'`（n_init=1）作为基准线。
- 短结论：均匀随机选种需要多少 `n_init` 才能让其**最差情况**（跨种子 max inertia）追平 k-means++ 单次的均值（"追平" = max(random@N) ≤ mean(++)，即 N 解锁"上界 vs 期望"的平衡）。

把以上写到 `./summary_kmpp_06_n_init_recovery.md`。

---

[Judge]

Look at `./summary_kmpp_06_n_init_recovery.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 `init='random'` 在 `n_init ∈ {1, 2, 5, 10, 20, 50, 100}` 下 inertia 跨 ≥ 30 种子的**均值 ± 标准差 + 最大值**；以及 `init='k-means++'`（n_init=1）作为基准。
2. 明确报告**均匀随机选种需多少 n_init 才能让 `max(random@N) ≤ mean(k-means++)`**——给出一个具体 N（如 5–20 之间），并以表格 / 曲线形式呈现"max vs N"和"mean(++) 基准线"的交叉点。
3. 短结论说明**k-means++ 单次 vs 随机选种 N 次重启动**的 trade-off（k-means++ 单次成本 = 1 次选种 D² 加权 + Lloyd 迭代；random@N = N 次选种 + N 次 Lloyd 迭代取最佳），并量化指出"k-means++ 等价于多少倍 random 重启"（如 N=1 的 k-means++ 大致等价于 N=5–20 次 random 重启的期望）。
