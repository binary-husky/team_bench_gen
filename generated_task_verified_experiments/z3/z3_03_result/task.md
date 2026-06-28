[Agents]

读给定材料，做实验，写结论。

考察 z3 求解 N-皇后问题的规模扩展性。用 z3-solver：变量为每行一个 Int 列号（域 1..N），施加列互不相同与对角线互不相同约束（或等价的布尔编码）。对 N ∈ {8, 10, 12, 15, 20} 分别求解（找第一个解），记录求解时间（固定随机种子/求解器设置；可设超时上限，如 120 秒）。把「求解时间 随 N 的变化」写到 ./summary_nqueens_scaling.md。固定设置：编码方式、求解器设置、超时上限；唯一自变量为 N。

---

[Judge]

Look at `./summary_nqueens_scaling.md`, check whether conclusion cover the following points

1. 求解时间随 N 增大而上升。
2. 增长呈超多项式/指数级（NP-难）。
3. z3 能解中等规模 N，但在较大 N 处撞上扩展性墙。
