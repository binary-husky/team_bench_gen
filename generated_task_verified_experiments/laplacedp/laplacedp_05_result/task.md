[Agents]

读给定材料，做实验，写结论。

考察查询敏感度 Δf 对噪声/效用的影响。固定 ε，对一组不同敏感度的查询分别加噪：(a) 计数查询（Δf=1）；(b) 区间 [0,B] 上的求和查询（Δf=B，如 B=10）；(c) n 个数据上的均值查询（Δf=1/n）。用 Laplace 机制（scale=Δf/ε），重复多次，记录各自的平均绝对误差。把「误差随查询敏感度 Δf 的变化」写到 ./summary_sensitivity.md。固定设置：ε、数据规模、试验次数、随机种子；自变量为查询类型（即 Δf）。

---

[Judge]

Look at `./summary_sensitivity.md`, check whether conclusion cover the following points

1. 敏感度越大的查询，所需噪声越大、误差越大。
2. 误差量级随 Δf 线性增长（~Δf/ε）。
3. 高敏感度查询在同等 ε 下效用更差。
