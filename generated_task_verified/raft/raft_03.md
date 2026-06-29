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


[Judge V2]

查阅 `./summary_raft_03_replication_commit.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；进程内仿真、1000 entry、N∈{3,5}、≥5 种子）：

1. 须给 N=3/N=5 下 1000 条 entry 提交时延(均值/中位/最大)+全部提交比例+commitIndex 单调不减、≥5 种子（golden：N=3 mean3.16/med3/max5.60、N=5 mean3.41/med3/max5.20、100% 提交、0 回退；可接受：≥5 种子、100% 提交、0 回退）。（细化原 [Judge] 第 1 点）
2. 须给每条被提交 entry 先在严格多数节点复制（提交严格发生在多数复制后）（golden：N=3 复制 mean2.0/min2、N=5 mean3.0/min3、提交时皆达严格多数；可接受：提交时达严格多数）。（细化原 [Judge] 第 2 点）
3. 须给 N=5 时延 > N=3（需更多 ACK）+全部提交无丢失（golden：N=5 mean3.41 > N=3 3.16、分布右移；可接受：N=5 > N=3）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
