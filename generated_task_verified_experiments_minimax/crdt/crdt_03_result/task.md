[Agents]

读给定材料，做实验，写结论。

用 Python **进程内**实现 state-based CRDT（G-Counter、PN-Counter、OR-Set、LWW-Register）的 `merge`；另实现一个**朴素非 CRDT 对照**（如普通整数计数器，`update` 为 `+=`、`merge` 为顺序敏感的累加或覆盖）。

研究目标：**验证 CRDT 的 `merge` 在消息乱序与重复投递下仍收敛到同一状态（交换+结合+幂等）；对照地，朴素非 CRDT 的最终状态依赖投递顺序/重复。**

固定实验设置（不要更改）：
- 准备一份固定的"状态/操作消息集合"（如若干副本各自的 G-Counter 向量、OR-Set 的 add 操作集等，由确定种子生成）。
- 对**同一**消息集合，构造 **≥ 100 种不同的投递方案**：(a) 随机**全排列**投递顺序；(b) 额外对部分消息做**重复投递**（同一条 merge 消息投递 2 次或多次）。
- 对每种 CRDT 与每种投递方案，把消息依次 `merge` 进一个聚合副本，记录**最终状态**。
- 对朴素非 CRDT 计数器做同样实验作为对照。

需要记录/报告的指标：
- 每种 CRDT 在 ≥100 种乱序+重复方案下得到**不同最终状态的个数**（CRDT 应为 **1**）；对照朴素计数器得到的不同最终状态个数（应 > 1，受顺序/重复影响）。

把以下内容写到 `./summary_crdt_03_order_invariance.md`：
1. 表/图：每种 CRDT 的"不同最终状态个数"（乱序+重复下），与朴素计数器对照。
2. 结论要点：CRDT 在所有乱序+重复方案下最终状态**唯一**（合并满足交换+结合+幂等）；朴素计数器最终状态**随顺序/重复而变**，从而无法在异步可乱序/重复的网络下收敛。

---

[Judge]

Look at `./summary_crdt_03_order_invariance.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了在 ≥100 种乱序+重复投递方案下，每种 CRDT（G-Counter/PN-Counter/OR-Set/LWW-Register）得到的**不同最终状态个数 = 1**，以表格呈现。
2. **对照实验**：朴素非 CRDT 计数器在同样乱序+重复下得到**多于一个**的最终状态个数（随投递顺序/重复而变），说明 CRDT 的不变性来自 merge 的交换+结合+幂等。
3. 明确把"最终状态唯一"归因于 `merge` 满足**交换+结合+幂等**三性（乱序↔交换+结合；重复↔幂等），这正是 CRDT 能在不可靠/乱序/重复网络下收敛的结构原因。

---

[Judge V2]

查阅 `./summary_crdt_03_order_invariance.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准）：

1. 须给 ≥100 方案下每 CRDT 仅 1 终态（golden：200 方案全 =1、G-Counter=32/PN=27/LWW=v7/OR-Set={a,b,c,d}；可接受：≥100 方案且 =1）。（细化原 [Judge] 第 1 点）
2. 须给朴素基线发散（golden：Δ-counter 41、overwrite 7；可接受：朴素 >1 即发散）。（细化原 [Judge] 第 2 点）
3. 须归因 merge 三律——四 CRDT 过交换/结合/幂等微断言（golden：True×3；可接受：通过三律微断言）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
