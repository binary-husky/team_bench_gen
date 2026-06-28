[Agents]

读给定材料，做实验，写结论。

考察 ε 对实用性的影响（隐私-效用权衡）。固定一个计数/均值查询（Δf 固定），对 ε ∈ {0.01, 0.1, 0.5, 1, 2, 5} 分别：用 Laplace 机制（scale=Δf/ε）对查询输出加噪，重复多次，记录输出相对真值的平均绝对误差（MAE）与均方根误差（RMSE）。把「MAE/RMSE 随 ε 的变化」并与理论噪声尺度 Δf/ε 对比，写到 ./summary_utility_vs_epsilon.md。固定设置：查询、Δf、试验次数、随机种子；唯一自变量为 ε。

---

[Judge]

Look at `./summary_utility_vs_epsilon.md`, check whether conclusion cover the following points

1. 误差随 ε 增大（隐私减弱）而下降。
2. 误差量级符合 ~Δf/ε（Laplace 标度）。
3. 体现隐私-效用权衡。
