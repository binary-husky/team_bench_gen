[Agents]

读给定材料，做实验，写结论。

对比 z3 的可满足性求解与优化求解。构造一个小型约束优化问题（例如：若干带整数变量的调度/资源分配，在若干线性约束下最小化 makespan 或最大化某个线性目标；固定实例）。分别：(a) 用 z3-solver 的 Solver 找一个可行解（sat）；(b) 用 z3 的 Optimize 求目标的最优值（minimize/maximize）。记录可行解的目标值、最优目标值，以及两种求解各自的时间。把「可行解 vs 最优解 的目标值与时间对比」写到 ./summary_optimize.md。固定设置：问题实例、变量域、约束、z3 设置；自变量为求解模式（sat vs optimize）。

---

[Judge]

Look at `./summary_optimize.md`, check whether conclusion cover the following points

1. Optimize 求得的目标值优于（不劣于）任意可行解（确为最优）。
2. 优化求解耗时多于仅求可满足性。
3. 最优解满足所有约束。
