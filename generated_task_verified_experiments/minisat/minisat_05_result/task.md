[Agents]

读给定材料，做实验，写结论。

考察「图着色」这一结构性 SAT 应用的求解难度。用 networkx 生成随机图 G(n, p)（n ∈ {10, 15, 20}，p=0.5，每档若干随机种子）。把「图 G 是否 k-可着色」编码为 CNF（每个顶点至少一种颜色；相邻顶点颜色不同；用逐步递增 k 的方式扫描）。对每个图，扫描颜色数 k = 1, 2, 3, …，用 PySAT 的 MiniSAT 判定可满足性，直到首次 SAT，从而得到色数 χ(G)，并记录每个 k 的冲突数与时间。把「冲突数/时间 随 k 的变化（在 k 接近 χ 时最难）以及随图规模 n 的变化」写到 ./summary_graph_coloring.md。固定设置：n 取值、p=0.5、随机种子、CNF 着色编码、求解器；自变量为 k 与 n。

---

[Judge]

Look at `./summary_graph_coloring.md`, check whether conclusion cover the following points

1. 当 k ≥ χ(G) 时实例为 SAT 且较易（冲突少、快）。
2. 当 k < χ(G) 时为 UNSAT，且难度在 k 接近 χ 时达到峰值（边界处最难）。
3. 冲突数随图规模 n 增大而增大。
