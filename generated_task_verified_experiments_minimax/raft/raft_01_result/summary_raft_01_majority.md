# 为什么 Raft 必须用"严格多数（strict majority）"而不能用"相对多数（plurality）"

> 推理范围：纯逻辑推理（无代码实验）。所有论证都基于论文中给出的两条规则
> ——（a）每个 term 内一名候选人必须获得**严格多数**票（> N/2）才能当选；
> （b）每个节点在一个 term 内**至多投一票**（先到先得）。
> 下文把"严格多数"放宽为"相对多数"后，逐级推演它会断裂哪条安全保证。

---

## 0. 记号

- 集群节点总数 = N（通常 N = 2F+1，例如 N=5 容忍 2 个故障）。
- 候选人集合 C。term T 内的投票函数 `vote : 节点 → C ∪ {null}`，满足 `|{s : vote(s)=c}|` 是候选人 c 在 term T 得到的票数。
- 规则（b）：∀ c₁ ≠ c₂，{投 c₁} ∩ {投 c₂} = ∅（每个节点至多投一票）。
- 规则（a·strict）：c 当选 ⟺ |{投 c}| > N/2。
- 规则（a·plurality，假想放宽版）：c 当选 ⟺ ∀ c' ≠ c，|{投 c}| ≥ |{投 c'}|（票数最多者胜，不必过半）。

---

## 1. 鸽巢 / 集合相交论证：严格多数 ⇒ 同一 term 至多一人当选

**命题**：在同一个 term 内，最多只有一名候选人能获得严格多数。

**证明（反证 + 集合不相交）**：设同一 term 内有两名不同候选人 A、B 都获得严格多数票。
- 由规则（a·strict）：|投 A| > N/2 且 |投 B| > N/2。
- 把两式相加：|投 A| + |投 B| > N/2 + N/2 = N。
- 由规则（b）——每个节点至多投一票——集合 {投 A} 与 {投 B} **不相交**。
- 对不相交集合：|投 A ∪ 投 B| = |投 A| + |投 B|。
- 但 {投 A} ∪ {投 B} ⊆ 全集群节点集，|投 A ∪ 投 B| ≤ N。
- 因此 N < |投 A| + |投 B| = |投 A ∪ 投 B| ≤ N —— 矛盾。

结论：同一 term 内**不可能**有两人同时拿到严格多数。这一性质就是论文 Figure 3 中的 **Election Safety**："at most one leader can be elected in a given term"（§5.2）。该条性质的成立**完全依赖**于"严格多数 + 每节点一票"这一对组合，单靠"每节点一票"是不够的。

### 为什么 plurality 让这一步立即崩溃
plurality 只要求"得票最多"，所以只要节点把票分散投给多个候选人，**任何低于 N/2 的票数都可能胜出**。最关键的：plurality 不再给"两个胜者票数之和"设下任何上界。
- 反例：N=5 集群分裂成 {s1,s2} 与 {s3,s4,s5}。如果 s1、s2 互相投票，s1 得 2 票；s3、s4、s5 互相投票，s3 得 3 票。s3 在 s3,s4,s5 子集内是"最多票者"，但更糟的是——s1 在 {s1,s2} 子集内也是"最多票者"（没人比他多），**两个子集选出两个 leader** 完全可能。
- 注意严格多数论证里的关键不等式 |投 A|+|投 B| > N 在 plurality 下**根本无法写出**，因为两个"最多票者"各自的票数都 ≤ N/2，其和甚至可能 < N（最极端情况：N=5，A 得 2 票、B 得 2 票、和=4<N），鸽巢论证里那个"和 > N"的不等式直接消失。

---

## 2. "每 term 至多一个 leader" 是日志一致性的前提

Raft 的安全性最终要落到 **State Machine Safety**（§5.4.3）——"if a server has applied a log entry at a given index to its state machine, no other server will ever apply a different log entry for the same index"（同一 index 上所有状态机看到同一条命令）。这一保证的证明链依赖若干性质，而 **Election Safety** 是最底下的那条：

```
Election Safety   (同一 term 至多一个 leader)
      │
      ▼
Leader Append-Only（leader 只追加、不删改日志） +  Log Matching（先导一致性）
      │
      ▼
Leader Completeness（已提交 entry 在所有更高 term 的 leader 日志里）
      │
      ▼
State Machine Safety（同一 index 同一命令）
```

每一条性质都靠**前一条**的证明细节；去掉 Election Safety，链条直接倒。

### plurality 下的反例：同一 term 两个 leader → 两条冲突日志

设想 N=5 集群 {s1,s2,s3,s4,s5}，term T 内发生网络分区 {s1,s2} | {s3,s4,s5}：
1. s1 发起选举，{s1,s2} 互投 → s1 得 2 票，是子集内"最多票者"，自封 leader，term=T。
2. 几乎同时 s3 发起选举，{s3,s4,s5} 互投 → s3 得 3 票，是子集内"最多票者"，自封 leader，term=T。
3. 同一个 term T，**集群里同时有两个 leader**：s1 和 s3。
4. 客户端向两边各自提交不同命令：s1 把 x=8 append 到自己的日志；s3 把 x=9 append 到自己的日志。
5. 两条 log entry 都标 (index=k, term=T)，但命令不同。
6. 分区愈合：s1 和 s3 中只能有一个继续当 leader（假设 s3 赢得下一个 term）。s1 的 (k, T, x=8) 与 s3 的 (k, T, x=9) **日志在 index=k 处冲突**。
7. 按 Raft 的 AppendEntries 协议，新 leader 会强制 follower 的 log 跟自己一致（删除冲突、保留自己的），于是 s1 之前那条 (k, T, x=8) 被 s3 的 (k, T, x=9) 覆盖、丢失。
8. 如果 s1 在分区期间已经把 x=8 应用到了本地状态机并返回给客户端"成功"，s3 的集群在愈合后却应用了 x=9 ——**两台状态机对同一 index 给出了不同结果**，State Machine Safety 被破坏。

这一切之所以会发生，根因是 plurality 让 Election Safety 不再成立。**两个 leader 在同一 term 各自 append 互不相同的 entry**，后续所有"日志只从 leader 流向 follower"的修复都只能保证"新 leader 视角下的日志一致"，而**已经被旧 leader 应用过的命令可能已在另一分片被另一组"已提交多数"接受**——丢失与分歧都可能出现。

---

## 3. 严格多数 ⇒ 任意两个"已提交多数集合"必然相交 ⇒ Leader Completeness

Leader Completeness（§5.4）原文："if a log entry is committed in a given term, then that entry will be present in the logs of the leaders for all higher-numbered terms."

**为什么需要"严格多数"才能证它？** 论文 §5.4.3 的证明结构如下（提纯版）：

1. 反设某 term T 提交的 entry e **不**在 term U（U > T）的 leader L_U 的日志里。
2. L_U 当选时获得了一组选票 S_L —— 由 RequestVote 规则，**只有当 S_L 里的某节点自己的 log 至少与 L_U 一样新**时才会投赞成票。这意味着 S_L 里**每个**节点的 lastLogTerm、lastLogIndex ≥ L_U 当时声称的。
3. 而 e 在 term T 被提交时已存在于一组节点 S_e 上 —— 严格多数：|S_e| > N/2。
4. 选新 leader L_U 时，S_L 也满足严格多数：|S_L| > N/2。
5. 鸽巢：|S_e| + |S_L| > N，而 S_e、S_L 是节点集的子集且必然**有非空交集** ∃v ∈ S_e ∩ S_L。
6. v 既在 e 的多数集里（持有 e），又投了 L_U（因此 v 的 log 至少与 L_U 一样新）。但 L_U 的 lastLogIndex < e.index（反设 L_U 没有 e），矛盾。
7. 因此 L_U 必然持有 e。

证明第 5 步里那个**"两个严格多数集合必然相交"**的断言，靠的就是 |S_e| > N/2 且 |S_L| > N/2 ⇒ 交集非空。这是严格多数数学性质的直接推论：**任意两个严格多数集合在 N 个节点的集合论下必交**。

### plurality 让这条传递链彻底断裂

把规则换成 plurality 后：
- 提交 e 时的"多数"不再是严格多数 —— 可能只是 e 的候选 leader 的"最多票子集"。极端情况下，e 只被存在 N/2 + 1 个节点上（用 Raft 原本的"复制到多数"语义）或更少（如果进一步把 commit 规则也放宽）。
- 选出新 leader L_U 时的"多数"同样只是 S_L ⊆ 节点集，|S_L| 不再保证 > N/2。
- **S_e 与 S_L 完全可能不相交**。反例：N=5，e 落在 {s1,s2}，选出 L_U 的票源是 {s3,s4}（s5 投了别人或弃权），两集合无交集。
- 这时根本找不到一个既持有 e、又投了 L_U 的"见证者"v，证明第 5 步的鸽巢论证失效。
- L_U 的日志里**完全可以不包含 e**，却仍然当选为 leader。Leader Completeness 被破坏。
- 一旦 Leader Completeness 不成立：e 之后可能在新 leader 上被覆盖；不同分片对同一 index 提交不同命令；State Machine Safety 跟着失守。

**传递链的断裂点就在第 5 步**：严格多数 → "两严格多数集合必相交" → 选 leader 时必有一个"同时持有 e"+"log 够新"的节点能投它；plurality → 多数集合可以不相交 → 找不到这样的见证者 → Leader Completeness 的证明失效 → State Machine Safety 失效。

---

## 4. 结论（一句话）

**Raft 必须用严格多数而不能用 plurality**，是因为"严格多数"是 Election Safety（同一 term 至多一个 leader）和 Leader Completeness（已提交 entry 永不丢失）这两条核心安全保证的共同数学基石——只有它能保证任意两个相关节点集合必然相交，从而在选举/提交事件之间架起"鸽巢桥"；一旦换成 plurality，这个交集不再必然出现，Election Safety 与 Leader Completeness 同步崩塌，并最终撕裂 State Machine Safety，使同一 index 在不同状态机上可能产生不同的命令结果，Raft 的全部安全性就荡然无存。
