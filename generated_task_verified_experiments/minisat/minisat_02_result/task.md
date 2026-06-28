[Agents]

读给定材料，做实验，写结论。

考察随机 3-SAT 在相变点附近的求解难度。固定变量数 n=50，改变子句/变量比 α = m/n ∈ {3.0, 3.5, 4.0, 4.267, 4.5, 5.0, 6.0}；对每个 α 随机生成约 15 个 3-SAT 实例（DIMACS CNF，随机种子 0..14），用 PySAT (pip install python-sat) 的 MiniSAT 求解器（Solver(name='Minisat22')）逐一求解，记录每个实例的冲突数（conflicts）与求解时间。计算每个 α 下的平均冲突数与平均时间，以及可满足（SAT）实例占比。把「平均冲突数 / 平均时间 / SAT 占比 随 α 的变化」写到 ./summary_phase_transition.md。固定设置：n=50、上述 α 取值、随机种子、求解器；唯一自变量为 α。

---

[Judge]

Look at `./summary_phase_transition.md`, check whether conclusion cover the following points

1. 平均冲突数/时间在 α≈4.2–4.3（3-SAT 相变点）附近出现明显峰值（最难）。
2. α 明显低于相变点时实例多为 SAT 且容易（冲突少）。
3. α 远高于相变点后实例多为 UNSAT 且难度回落（过度约束、易于反驳）。
