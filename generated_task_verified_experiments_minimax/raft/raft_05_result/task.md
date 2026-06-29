[Agents]

读给定材料，做实验，写结论。

使用同款**进程内 Raft 仿真器**（Python、内存队列、逻辑 tick 时钟、确定性种子、无真实网络/socket/Docker）。仿真能**按需隔离/恢复**某节点与其余节点的消息通路（即模拟网络分区），其余行为复现 Raft 选举与日志复制。

研究目标：**验证 term（任期）机制下的日志安全——被罢免/旧 term 的 leader 无法覆盖/破坏已被新 term 提交的条目（Leader Completeness 的运行期体现）。**

固定实验设置（不要更改）：
- 集群 **N = 5**。场景脚本：
  1. 正常选出 leader L1（term T），提交若干条目（设 **50** 条）并确认提交。
  2. **隔离 L1**（断开它与多数节点的消息），使其无法再获多数。
  3. 其余节点选出新 leader L2（term T' > T），L2 提交 **新条目**（设 50 条）并确认提交。
  4. **恢复 L1 的连接**：L1 用其旧 term T 尝试 AppendEntries。
- 用 **≥ 10 个不同随机种子**重复（每种子重新生成条目内容、决定分区时机）。

需要记录/报告的指标（每次重复）：
- L1 恢复连接后是否被**强制降级为 follower**（因其 term T < T'，收到更高 term 的消息即降级）；
- **已提交条目完整性**：L2 在 term T' 提交的条目是否被 L1 的旧 AppendEntries **覆盖/破坏**（应为 0 条被破坏）；
- L1 中**未提交的陈旧条目**（L1 在隔离期间 append 但未提交的）是否被**截断**以匹配 L2 的日志（log reconciliation / truncate）。

把以下内容写到 `./summary_raft_05_term_safety.md`：
1. 表：每次重复的"L1 是否降级""已提交条目被破坏数""陈旧未提交条目被截断数"。
2. 结论要点：L1 恢复后**必然降级**；新 term 已提交条目**0 条被破坏**（Leader Completeness 在运行期成立）；L1 的陈旧未提交条目被正确截断以对齐 L2。整轮 **< 30 分钟**。

---

[Judge]

Look at `./summary_raft_05_term_safety.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了每次重复（≥10 种子）的"L1 是否降级为 follower""已提交条目被破坏数""陈旧未提交条目被截断数"，以表格呈现。
2. **L1 恢复连接后必然降级为 follower**（旧 term T < T'，遇到更高 term 即降级），旧 term 的 AppendEntries 不再被接受为权威——即"被罢免的 leader 无法继续用旧 term 主导"。
3. **新 term 已提交条目 0 条被破坏**（Leader Completeness 在运行期成立）；且 L1 在隔离期 append 的**陈旧未提交条目被正确截断**以对齐新 leader L2 的日志（log reconciliation）。两者共同验证 term 机制下的日志安全。


[Judge V2]

查阅 `./summary_raft_05_term_safety.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；进程内仿真、隔离旧 leader L1、新 leader L2 term T′>T、≥10 种子）：

1. 须给每次重复(≥10 种子) L1 是否降级/已提交条目被破坏数/陈旧未提交条目截断数表（golden：12/12 种子 L1 降级、破坏 0、截断==k、lastLogIndex=100/commitIndex=100；可接受：≥10 种子、表格）。（细化原 [Judge] 第 1 点）
2. 须给 L1 恢复后必然降级 follower（旧 term T<T′ 遇更高 term 即 step_down）（golden：12/12 降级、currentTerm=T′；可接受：必然降级）。（细化原 [Judge] 第 2 点）
3. 须给新 term 已提交条目 0 破坏(Leader Completeness) + 陈旧未提交条目正确截断对齐 L2（golden：破坏 0、截断==k 且均为未提交(>原 commitIndex=50)；可接受：0 破坏 + 截断未提交条目）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
