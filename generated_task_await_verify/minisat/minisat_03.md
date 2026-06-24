[Agents]

读给定材料，做实验，写结论。

考察「冲突驱动子句学习」相对于「无学习的朴素 DPLL」的威力。自己实现一个朴素 DPLL（含单元传播 + 按时间顺序回溯，但【不做】子句学习、不做 VSIDS、不做重启）。生成小规模随机 3-SAT：n ∈ {15, 20, 25}，α≈4.2，每个 n 取 5 个随机种子。对每个实例分别用朴素 DPLL 与 PySAT 的 MiniSAT（CDCL）求解（单实例超时上限 60 秒，超时记为 timeout）。记录朴素 DPLL 的决策数（decisions）与 MiniSAT 的冲突数/决策数，以及各自用时。把「DPLL vs MiniSAT 的决策/冲突数与时延、随 n 的变化」写到 ./summary_cdcl_vs_dpll.md。固定设置：n 取值、α≈4.2、随机种子、单实例 60 秒上限；自变量为 n 及求解器对比。

---

[Judge]

Look at `./summary_cdcl_vs_dpll.md`, check whether conclusion cover the following points

1. CDCL（MiniSAT）的冲突数/决策数比朴素 DPLL 少若干个数量级。
2. 朴素 DPLL 的决策数随 n 增长极快（指数级），而 CDCL 增长远缓。
3. 两者差距随 n 增大而急剧拉大（学习对搜索空间的剪枝随规模放大）。
