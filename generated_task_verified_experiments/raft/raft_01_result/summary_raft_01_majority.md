# 为什么 Raft 选举需要严格多数而非相对多数（plurality）

> 任务要求：仅逻辑推理（不做实验）回答——为何候选人需获**严格多数**（票 > N/2）才能当选，且每节点一 term 至多一票。推理鸽巢安全性、plurality 的日志分叉、以及严格多数 ⇒ Leader Completeness。
> 依据 Ongaro & Ousterhout, *In Search of an Understandable Consensus Algorithm* (USENIX ATC 2014)。

---

## (a) 鸽巢论证：同 term 至多一个候选人获严格多数

每节点在一个 term 内**至多投一票**（先到先得）⇒ 全网总票数 ≤ N。若同一 term 内有两个候选人各获严格多数（> N/2）票，两集合大小之和 > N/2 + N/2 = N。但两集合若不相交，其和 ≤ 总票数 ≤ N ——矛盾。故两集合必相交，而相交意味着同一节点给两个候选人都投了票，违反「一 term 一票」。因此：

> **同一 term 至多一个候选人能获严格多数** ⇒ 同 term 至多一个 leader 当选。

这是「单 leader 一致性」的数值根基。plurality（相对多数，最多票即可）没有此性质：多个分区可各自选出「本分区得票最多者」，同 term 出现多个 leader。

## (b) plurality 导致日志分叉

plurality 下，网络分区可使不同子集各自选出 leader。两个同 term 的 leader 向不同 follower 在**同一 log index** 复制**不同 entry** ⇒ 日志分叉/冲突。后续若两个 leader 都「认为」自己已提交该 index，就出现两个不一致的已提交值 ⇒ **违反单拷贝一致性**。严格多数保证同 term 单 leader，从源头杜绝这种分叉。

## (c) 严格多数集合两两相交 ⇒ Leader Completeness（已提交 entry 不丢）

两个 > N/2 的集合**必相交**（和 > N ⇒ 不可能不相交）。考虑任一**已提交** entry：它已被某个旧 term 的**严格多数**集合复制。新 leader 当选也凭一个**严格多数**集合。两严格多数集合必相交 ⇒ 新 leader 的集合中**至少有一个节点**持有该已提交 entry。配合**选举限制**（选民只给 log 至少一样新的候选人投票，拒绝 log 更旧者）⇒ 该节点必在新 leader 的更-log-中 ⇒ 新 leader 含该已提交 entry ⇒ **已提交条目在新 leader 任内不丢失**（Leader Completeness）。

plurality 下，多数集合不一定相交（如各占 40%、第三 20%），「相交 ⇒ 持有者进新多数」这一步**断裂** ⇒ 新 leader 可能不含已提交 entry ⇒ 已提交条目可丢。

## 一句话总结

每节点一 term 一票 + 严格多数(>N/2) ⇒ 鸽巢推出同 term 至多一个 leader（plurality 无此性质 ⇒ 分区多 leader ⇒ 同 index 不同 entry 日志分叉）；且两严格多数集合必相交 ⇒ 新 leader 集合必与旧已提交 entry 的多数集合相交、配选举限制 ⇒ 已提交 entry 不丢（Leader Completeness）；plurality 集合不一定相交，该传递链断裂 ⇒ 已提交 entry 可丢。故 Raft 用严格多数。
