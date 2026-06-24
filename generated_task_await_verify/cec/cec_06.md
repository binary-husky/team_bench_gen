[Agents]

复现 RCMAES 算法（./material），配置 python 环境。

研究 active covariance matrix adaptation（论文式 5，对差解赋负权重）在 RCMAES 框架下的必要性。固定种群缩减、restart、bound handling 等与 paper 默认一致。

至少对比以下 4 种 covariance update 规则，全部在 **CEC2022 D=20**（budget = 40000 evals）上跑：

1. `active`（paper）：rank-one + rank-μ（带正权重）+ active 项（对后 λ-μ 个差解赋负权重，见式 5）
2. `standard`：只做 rank-one + rank-μ（标准 CMA-ES，无 active 项）
3. `rank_one_only`：只做 rank-one update（c_μ = 0）
4. `rank_mu_only`：只做 rank-μ update（c_1 = 0）

每种 update 在全部 12 个 CEC2022 D=20 函数上跑 25 次。

记录每种 update 下：final E、C 矩阵条件数随 epoch 的变化、收敛 epoch。

按函数类型（basic / hybrid / composition）报告 average E。

把结论写到 `./summary_active_cma.md`。

---

[Judge]

Look at `./summary_active_cma.md`, check whether conclusion cover the following points:

1. active 在至少 7/12 个函数上 E 优于 standard
2. active 在 ill-conditioned 函数（F10-F12，composition 类型）上比 standard 改进 ≥ 5%
3. rank_one_only 是四种 update 中最差的（overall E 至少是 active 的 1.3 倍）
4. C 矩阵条件数：active 比 standard 下降更快（同 epoch 下条件数更小，说明 active 加速了 covariance 学习）
