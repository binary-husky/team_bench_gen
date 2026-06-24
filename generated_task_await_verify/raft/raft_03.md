[Agents]

读给定材料，做实验，写结论。

使用上一题同款的**进程内 Raft 仿真器**（Python、内存队列、逻辑 tick 时钟、确定性种子、无真实网络/socket/Docker）。复现 AppendEntries 日志复制与提交（commitIndex 推进）。

研究目标：**验证 Raft 日志复制机制——条目在多数节点上复制后即被提交（commit），commitIndex 单调推进。**

固定实验设置（不要更改）：
- 选定 leader 后（用合理超时参数避免 split-vote），向 leader 连续提交 **1000** 条客户端命令（命令内容可任意，如整数序列）。
- 节点数对比：**N = 3** 与 **N = 5** 各跑一组（其余参数同）。
- 网络假设：进程内全互联、消息按 tick 投递、无丢包（本题主测复制/提交机制本身，故障留待 _04/_05）。
- 每个 N 用 **≥ 5 个不同随机种子**重复。
- 记录：(a) 每个 entry 被复制到的节点数；(b) 是否被提交（commitIndex 是否覆盖到该 index）；(c) 每条 entry 的**提交时延**（从 append 到 commit 的逻辑 tick 数）；(d) commitIndex 是否单调不减。

把以下内容写到 `./summary_raft_03_replication_commit.md`：
1. 表/图：N=3 与 N=5 下，提交时延分布（均值/中位数/最大）、1000 条最终全部提交的比例、commitIndex 单调性（是否出现回退）。
2. 结论要点：所有 1000 条是否最终都被提交；被提交的条目是否都先在**严格多数**节点上完成复制；N=5 比 N=3 提交时延是否更大（需等更多节点确认）；commitIndex 是否全程单调不减。整轮 **< 30 分钟**。

---

[Judge]

Look at `./summary_raft_03_replication_commit.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 N=3 与 N=5 下 1000 条 entry 的**提交时延**（均值/中位数/最大）与**最终全部提交的比例**，commitIndex 是否**单调不减**（应全程不回退），基于 ≥5 种子。
2. **每条被提交的 entry 都先在严格多数节点上完成复制**（提交严格发生在多数复制之后，且只发生在多数复制之后），验证"多数复制即提交"。
3. **N=5 的提交时延大于 N=3**（需等待更多节点确认 ACK），并给出具体数值比较；且全部 entry 最终都被提交（无丢失）。
