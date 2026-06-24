[Agents]

读给定材料，做实验，写结论。

自行实现一个**进程内 Raft 仿真器**（从给定材料中的论文出发用 Python 实现）：3–5 个逻辑节点，消息经**内存队列**传递，使用**逻辑/虚拟时钟**（以 tick 为单位推进，所有超时以 tick 计），**确定性随机种子**，**不使用任何真实网络 / socket / Docker / 多机**。节点状态机复现 Follower / Candidate / Leader 三态 + 选举（RequestVote）+ 心跳。

研究目标：**随机化选举超时（election timeout）的"离散度（spread）"如何决定选出 leader 的速度与 split-vote（瓜分选票、无人过半）的发生率。**

固定实验设置（不要更改）：
- 集群规模固定 **N = 5** 节点；初始全部 Follower，term=0，无 leader。
- 选举超时：每个节点从一个区间 `[T_min, T_max]` 均匀采样（单位：tick）；心跳间隔固定（如 `H = T_min / 3`）。
- 扫描超时**离散度**：`spread = T_max − T_min`，取网格 **spread ∈ {0, 1·H, 5·H, 10·H, 20·H}**（spread=0 即所有节点同一超时、必然同时发起选举）。
- 每个 spread 用 **≥ 30 个不同随机种子**重复一次"冷启动选举"。
- 每次记录：(a) **time-to-elect**：从启动到出现唯一 leader 的逻辑 tick 数；(b) 是否发生 **split-vote**（某 term 内无候选人获严格多数，需要升 term 重试）。

需要记录/报告的指标（每个 spread）：
- **median time-to-elect**（跨种子）；
- **split-vote 发生率**（发生 split-vote 的种子占比）。

把以下内容写到 `./summary_raft_02_election_spread.md`：
1. 一张表/图：每个 spread 下的 median time-to-elect 与 split-vote 率。
2. 结论要点：spread=0 时 split-vote 率是否接近 1（几乎必瓜分）；随 spread 增大 split-vote 率是否快速下降至接近 0、time-to-elect 是否稳定在一个小值附近（如量级在 `~T_max`）。整轮 **< 30 分钟**。

---

[Judge]

Look at `./summary_raft_02_election_spread.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了每个 spread `{0,1H,5H,10H,20H}` 下 **median time-to-elect** 与 **split-vote 发生率**（基于 ≥30 种子），以表格或图呈现。
2. **spread=0 时 split-vote 率接近 1**（节点同时发起选举、瓜分选票无人过半）；随 spread 增大，split-vote 率**快速下降至接近 0**。
3. 随 spread 增大，median **time-to-elect 稳定**在一个不大的值附近（量级约 `T_max`），即随机化超时以很小的额外时延换来几乎无 split-vote——这正是 Raft 用随机化超时避免瓜分的核心收益。
