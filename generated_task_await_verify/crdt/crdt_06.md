[Agents]

读给定材料，做实验，写结论。

考察 **网络分区恢复后** CRDT 的收敛行为：3 个副本在分区期间各自独立累积 update，分区愈合（merge 全部累积状态）后是否**收敛到同一状态**——验证 Shapiro et al. 2011 §3.1 的 SEC 性质在分区场景下仍成立。

固定实验设置（不要更改）：
- CRDT 类型：state-based G-Counter、PN-Counter、OR-Set（沿用 _02 的实现）。
- 副本数：3（每个副本各自维护本地状态 + 一个可接收 merge 的 `merge` 接口）。
- 实验流程（每个 CRDT 类型分别跑）：
  1. **T0**：三个副本都从空状态开始。
  2. **T1 — 分区**：将 3 副本切分为三组，每组单独运行 `R ∈ {50, 100, 200, 500}` 次 update（按 G-Counter：inc(r, x)；PN-Counter：inc/dec；OR-Set：add/remove 集合中各元素）。
  3. **T2 — 愈合**：依次 merge 三个副本的状态（a.merge(b); b.merge(c)），断言**所有副本最终状态完全一致**（SEC）。
- 每个 CRDT 类型 × 每个 R 用 **≥ 10 个不同随机种子**独立重复。
- 指标：
  - **SEC 收敛率**（最终三副本状态完全一致的比例）；
  - **最终状态的元素数量 / 总和**（验证合并后状态包含所有 update 的合并效果）；
  - 分区 + 合并总耗时。
- **仅 CPU**；整轮 **< 15 分钟**。

需要记录/报告的指标：
- 一张表：CRDT 类型 × R 的 SEC 收敛率（≥ 10 种子均值）。
- 一张图：R（update 数） vs SEC 收敛率（应恒为 1）。
- 短结论：**在 R=500 的高 update 计数下，所有 CRDT 类型的 SEC 收敛率仍为 100%**；并指出"分区不引入分歧、merge 是幂等 + 交换 + 结合 → 任意合并顺序得到相同终态"。

把以上写到 `./summary_crdt_06_partition_recovery.md`。

---

[Judge]

Look at `./summary_crdt_06_partition_recovery.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 G-Counter、PN-Counter、OR-Set 三种 CRDT 在 R ∈ {50, 100, 200, 500} 下的 **SEC 收敛率**（≥ 10 种子均值），以表格呈现。
2. 在所有 CRDT 类型 × 所有 R 上，**SEC 收敛率 = 1.0**（100% 一致）——验证分区后 merge 仍满足 SEC。
3. 短结论明确**分区 + 合并过程中 merge 调用总次数与 update 总数的关系**（对 G-Counter / PN-Counter：merge 接收方计数 = 所有其他副本的 max；对 OR-Set：union by add-wins），并量化最终状态规模与"无丢失"特性（所有 update 的效果都被保留）。
