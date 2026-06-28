[Agents]

读给定材料，做实验，写结论。

考察 **学习子句删除策略** 对 CDCL 求解器的影响：保留所有学习子句 vs 周期性 LRU 删除 vs 大小阈值删除。Een & Sörensson 2003 §4 提到 MiniSAT 默认保留学习子句，但实践中（Glucose / MapleSAT）会**定期清理 "less useful" 子句**——验证其动机：保留全部学习子句在长冲突链上对求解效率的损害。

固定实验设置（不要更改）：
- 求解器：使用 PySAT 的 `Minisat22` 或 `Glucose42`（已绑定 z3-solver 同源工具链），通过 PySAT 接口访问 `solver()` 句柄并支持 `conflicts / decisions / propagations` 计数。
- 任务集：随机 3-SAT 难例区（n=60, α=4.267）+ PHP 难例（n=5..7）+ 图着色难例（G(15, p=0.5), k=4）。
- 三种策略：
  - **(a) No-delete**：关闭 PySAT 求解器内部的清理（设置 `solver.conf_bounded = False` 或 `solver.conf_min_num_restarts` 控制，限制最大子句数）——可考虑直接保留所有学习子句（如选 MiniSAT22，因其默认无清理，最贴近论文 §4 行为）；
  - **(b) Glucose-style**：`solver = Glucose42()`，使用其默认的"基于 LBD"清理策略；
  - **(c) Manual LRU**：用 `solver.add_clause(...)` 后，每 `K=1000` 次冲突手动 `solver.remove_clause(...)` 删除最早添加的学习子句（前 500 条）。
- 每个 `(任务实例, 策略)` 跑一次（5 instances per family × 3 families = 15 instances × 3 strategies = 45 runs）。
- 时间上限：每 instance **30 秒**（用 PySAT 内部 `solver.conf_timeout` 或外层 signal）。
- **仅 CPU**；整轮 **< 30 分钟**。

需要记录/报告的指标：
- 一张表：每个 `(家族, 策略)` 的 `mean(conflicts)`、`mean(time_s)`、`#solved/5`（在 30s 内）。
- 短结论：**(a) vs (b)/(c)** 在 PHP 难例上 **conflicts 是否显著更多**（如 +50% 以上）、**time 是否更慢**（如 +30% 以上）；并指出"保留全部学习子句在长冲突链上确实带来开销，但并未改变 SAT/UNSAT 结果"。

把以上写到 `./summary_minisat_06_clause_deletion.md`。

---

[Judge]

Look at `./summary_minisat_06_clause_deletion.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了三个家族（3-SAT α=4.267 / PHP n=5..7 / 图着色 G(15,0.5) k=4）× 三个策略（No-delete / Glucose / LRU）共 9 个 cell 的 `mean(conflicts)`、`mean(time_s)`、`#solved/5`（30s 内），以表格呈现。
2. 在 PHP 难例上，**(a) No-delete** 相对 (b)/(c) **conflicts 至少多 30%**（或 #solved 至少少 1 个）——验证"保留全部学习子句在长冲突链上损害效率"的论点。
3. 三个策略在所有家族上**对 SAT/UNSAT 结论一致**（即清理策略只影响 cost，不影响可满足性结果）；并以一句短结论总结"清理学习子句是工程优化、不改变逻辑结果"。
