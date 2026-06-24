[Agents]

复现 HPO-B 基准（./material，论文 §5–7），配置 python 环境。

研究 Random Search vs 单一 Gaussian Process 在 4 种 acquisition function 下的差距，作为后续大型复现实验的小范围先行验证。

固定设置：
- 数据集 mode：`v3-test`（HPO-B-v3 的 meta-test split）
- search space 子集：只跑 evaluation 数最多的 3 个 search space，即 **`6766` (glmnet, 2 HPs)**、**`6794` (ranger, 10 HPs)**、**`6767` (xgboost, 18 HPs)**
- 每个搜索空间下跑全部 meta-test 数据集（论文 Table 3 列出：6766→6 个数据集、6794→6 个数据集、6767→6 个数据集），全部 5 个 seed（test0..test4）
- trial 数：每个 run 跑 100 个 trial（不含 5 个 seed 初始化）
- Random Search：均匀随机从 pending 集合中采样
- Gaussian Process：用 BoTorch `SingleTaskGP` + Matern 3/2 核（与论文 §7.1 一致），分别跑 `acq_name ∈ {EI, UCB, PI, PM}` 共 4 种 acquisition

输出：3 search space × 6 dataset × 5 seed × 5 method (1 RS + 4 GP-acq) × 100 trial = 共 4500 trial-level 数据点。

每个 (method, search_space, trial) 组合下：
1. 计算每个数据集上的 normalized regret（按论文 §6 定义，每任务用 (y*_max − y*_min) 归一化）
2. 计算每个数据集上的 rank（5 个方法跨数据集排名，1=最好）
3. 跨数据集与 seed 平均

把以下三件事写到 `./summary_rs_vs_gp.md`：

a. **3 个 search space 的 normalized regret 曲线**（trial 1..100）和 **平均 rank 曲线**（trial 1..100）——以图或表的形式。
b. 哪一种 acquisition（EI / UCB / PI / PM）在 3 个 search space 的整体平均上拿到最低的 normalized regret @100？与 Random Search 的差距是多少（百分点或相对差距）？
c. 18-HP 的 xgboost (6767) vs 2-HP 的 glmnet (6766)：哪种 search space 上 GP 的优势（相对 Random Search）更大？给出量化的 gap。

---

[Judge]

Look at `./summary_rs_vs_gp.md`, check whether conclusion cover the following points:

1. 在 3 个 search space 中的至少 2 个上，至少 1 种 GP acquisition 在 normalized regret @100 上比 Random Search 改善 ≥ 20%（相对差距）
2. 给出了 4 种 acquisition 在 3 个 search space 上的排名，并明确指出哪种 acquisition 是整体最优（不允许结论为"几乎一样"或"无差异"）
3. 给出了 "高维 xgboost vs 低维 glmnet" 上 GP 相对 RS 的 gap 对比，明确说出哪个 gap 更大以及具体数值（例如 glmnet gap = X，xgboost gap = Y，Y > X）
