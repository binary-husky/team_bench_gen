[Agents]

读给定材料，**不进行任何代码实验**，仅通过逻辑推理回答下面这一个问题，并把答案写到 `./summary_crdt_01_gcounter_decrement.md`。

背景：state-based CRDT 中 **G-Counter** 的结构是——状态为每副本计数向量 `v`（`v[i]` 是副本 `i` 的本地计数），偏序为逐分量 `≤`，`merge` 为逐分量 `max`（即任意两状态的 join/LUB），`increment` 把自身分量 `+1`。

---

**问题**（唯一一题）：

一位工程师想给 G-Counter 增加 `decrement`（自减）操作，让计数能下降。请从 state-based CRDT 的收敛原理出发，**逻辑推理为什么 G-Counter 的结构在原理上无法支持 decrement**。你的回答需覆盖以下推理链（给定材料的论文给出了 G-Counter 与 PN-Counter，但**没有**把下面这条"为何 G-Counter 不能自减"的完整论证作为结论直接写出）：

1. **state-based CRDT 收敛的两个结构前提**：(a) 状态更新必须**单调**——沿偏序只能上移（向 LUB 增长）、永不回退；(b) `merge` 必须是 join/LUB，满足**交换 + 结合 + 幂等**。说明这两条为何能保证"所有副本收到相同更新集合后状态相同"（强最终一致性 SEC）且**无需任何共识/协调**。
2. **decrement 与单调性冲突**：`decrement` 试图把某分量从 `c` 降到 `c−1`。证明：(i) 在偏序 `≤` 下这是一次**下降**，直接违反前提 (a) 单调性；(ii) 更根本地，`merge = max` 这个幂等的 join **无法传播下降**——一旦某副本已 merge 过分量值 `c`，则 `max(..., c) = c`，之后无论别的副本如何自减，再 merge 仍得 `max(c, c−1) = c`，下降被 `max` 吞掉、永久丢失。
3. **PN-Counter 如何"绕开"该限制**：用**两个** G-Counter `P`（计所有 increment）与 `N`（计所有 decrement），二者各自单调增长、`merge = 逐分量 max`，是合法 CRDT；最终值 `= P − N`。说明为什么这让 `P`、`N` 仍满足单调 + join 收敛，却通过"两个单调增量的代数差"实现可减计数。

最后给出一句结论：**为什么 G-Counter 不能 decrement，而 PN-Counter 能**。

---

[Judge]

Look at `./summary_crdt_01_gcounter_decrement.md`, check whether the answer covers the following **single evaluation dimension**（唯一一题，必须全对）：

1. **完整推理链**，必须同时出现：
    - **(a) 两条收敛前提**：状态更新**单调**（沿偏序只增不减）；`merge = join` 满足交换+结合+幂等。二者合 ⟹ "相同已交付更新集合 → 所有副本状态相同"（SEC）且**无需共识**。
    - **(b) decrement 与单调冲突 + max 无法传播下降**：`c→c−1` 是沿 `≤` 的下降，违反单调；且 `merge=max` 幂等，已 merge 进的 `c` 永远 `max(...,c)=c`，`max(c,c−1)=c`——下降被 max 吞掉、无法跨副本传播。
    - **(c) PN-Counter 的绕开**：用两个 G-Counter `P`、`N`，各自单调 + max-merge 仍是合法 CRDT，值 `= P − N`，以"两个单调增量之差"实现可减，而每个 G-Counter 本身不违反单调。
