# Term Safety under Leader Deposition (Leader Completeness, runtime)

## 实验概述

使用自建的**进程内 Raft 仿真器**（Python、内存消息队列、逻辑 tick 时钟、确定性种子、无真实网络/socket/Docker）验证 term（任期）机制下的日志安全。

- 集群 **N = 5**，多数 = 3。
- 消息通路可按需隔离/恢复：`isolated` 集合中的节点与其余节点之间的消息一律丢弃（网络分区）。
- 完整实现 Raft 选举（RequestVote，含 up-to-date 日志检查）、日志复制（AppendEntries，含 prevLogIndex/prevLogTerm 一致性检查、冲突回退、log reconciliation/truncate）、commit 推进（仅提交本 term 且已被多数复制的条目）、以及“收到更高 term 即降级为 follower”的规则。
- 代码：`./raft_sim.py`。12 个随机种子（≥10），每种子重新生成条目内容、陈旧条目数、分区时机。

### 固定场景脚本（每种子重复）

1. 正常选出 leader **L1**（term **T**），提交 **50** 条并确认在全部节点提交（commitIndex≥50）。
2. **隔离 L1**（断开它与多数节点的消息），使其无法再获多数。
3. 其余 4 节点选出新 leader **L2**（term **T′>T**）；L2 提交 **50** 条新条目（索引 51..100，term T′）并确认在多数节点提交（commitIndex≥100）。
   - 隔离期间 L1 作为旧 term leader 仍向自己日志 append 了 **k** 条陈旧未提交条目（索引 51..50+k，term T，无法获多数故未提交）。
4. **恢复 L1 的连接**：L1 仍以旧 term T 尝试 AppendEntries。运行足够长（800 tick）以观察降级 + 日志对齐。

## 结果表（每次重复）

| seed | T (L1) | T′ (L2) | 陈旧未提交条目数 k | L1 恢复后是否降级为 follower | 已提交条目被破坏数（新 51..100） | 旧已提交被破坏数（1..50） | 陈旧未提交条目被截断数 |
|----:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| 1  | 1 | 2 | 7 | 是 | 0 | 0 | 7 |
| 2  | 1 | 2 | 5 | 是 | 0 | 0 | 5 |
| 3  | 1 | 2 | 7 | 是 | 0 | 0 | 7 |
| 4  | 1 | 2 | 7 | 是 | 0 | 0 | 7 |
| 5  | 1 | 2 | 5 | 是 | 0 | 0 | 5 |
| 6  | 1 | 2 | 5 | 是 | 0 | 0 | 5 |
| 7  | 1 | 2 | 8 | 是 | 0 | 0 | 8 |
| 8  | 1 | 2 | 3 | 是 | 0 | 0 | 3 |
| 9  | 1 | 2 | 4 | 是 | 0 | 0 | 4 |
| 10 | 1 | 2 | 4 | 是 | 0 | 0 | 4 |
| 11 | 1 | 2 | 4 | 是 | 0 | 0 | 4 |
| 12 | 1 | 2 | 4 | 是 | 0 | 0 | 4 |

聚合校验：
- L1 恢复后**必然降级**为 follower（term 升至 ≥ T′）：**12/12**。
- 新 term 已提交条目（51..100, term T′）被 L1 旧 AppendEntries 破坏数：**0**（12/12）。
- 旧已提交条目（1..50, term T）被破坏数：**0**（12/12）。
- L1 陈旧未提交条目被截断以对齐 L2 日志：截断数 == k，**12/12**。
- L1 最终完成日志对齐（lastLogIndex≥100, commitIndex≥100）：**12/12**。

整轮仿真耗时 < 1 秒（远低于 30 分钟）。

## 结论要点

1. **L1 恢复连接后必然降级为 follower。** L1 在隔离期间保持旧 term T 的 leader 身份（leader 不触发选举超时，且收不到任何更高 term 的消息）。一旦连接恢复，L1 以 term T 发出的 AppendEntries 被处于 term T′>T 的节点拒绝，回复中携带更高的 term T′；L1 收到 `term > currentTerm` 的回复即按 Raft 规则 `step_down`，更新 currentTerm=T′、votedFor=None、state=follower。亦可由直接收到 L2 的 term-T′ AppendEntries 触发同样降级。两种路径均使 L1 失去 leader 身份。

2. **新 term 已提交条目 0 条被破坏 —— Leader Completeness 在运行期成立。** 被 L1 旧 term 的 AppendEntries “覆盖/破坏”在机制上不可能发生：
   - L1 的 AppendEntries 携带 term T < 接收方 currentTerm=T′，接收方在 `on_append_entries` 首步即返回 `success=False` 并丢弃载荷，**绝不修改本地日志**。
   - 故 L2 在 term T′ 已提交的 50 条（索引 51..100）在所有节点保持 (term=T′, 原始 cmd) 不变（破坏数=0）；L1 最初提交的 50 条（索引 1..50, term T）同样完好（破坏数=0）。
   - 根因是 Raft 的两条不变量在此叠加：（a）AppendEntries 的 term 门槛——低 term 无法写入高 term 节点；（b）Leader Completeness——任何被选出（获多数票）的 leader，其日志必不落后于任一已提交条目（RequestVote 的 up-to-date 检查保证了只有持有全部已提交条目的节点才能当选）。因此 L2 必然含有 L1 已提交的全部条目，新提交的条目又只增不改旧条目，旧 leader 无法回退之。

3. **L1 的陈旧未提交条目被正确截断以对齐 L2（log reconciliation / truncate）。** L1 隔离期间 append 的 k 条陈旧条目（索引 51..50+k，term T，未提交）在恢复后由 L2 的 AppendEntries 驱动对齐：L2 以 `prevLogIndex=50, prevLogTerm=T` 命中 L1 日志第 50 条（匹配），随后发送索引 51..（term T′）的条目；L1 在索引 51 处发现 `log[51].term=T ≠ T′`，按 Raft 规则从该点**截断**自身日志并追加 L2 的条目。全部 k 条陈旧条目被替换/移除（截断数 == k），L1 最终 lastLogIndex=100、commitIndex=100，与 L2 完全一致。被截断的均为**未提交**条目（索引 > 原 commitIndex=50），不违反任何已提交条目的完整性。

综上，在 12 个独立随机种子下，term 机制一致地保证了：旧 term 的被罢免 leader 既无法破坏新 term 已提交的日志（Leader Completeness 的运行期体现），其隔离期间产生的陈旧未提交条目也会在连接恢复后被精确截断以与新 leader 对齐。
