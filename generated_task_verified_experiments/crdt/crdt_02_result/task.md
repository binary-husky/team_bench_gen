[Agents]

读给定材料，做实验，写结论。

用 Python **进程内**实现若干 state-based CRDT：G-Counter、PN-Counter、G-Set、OR-Set、LWW-Register（每个含本地 `update` 与 `merge`，`merge` 为对应 join：逐分量 max / 集合并 / 带时间戳覆盖等）。**不使用任何真实网络**——副本为内存对象，消息经内存队列在拓扑上交换。

研究目标：**验证强最终一致性（SEC）——所有副本在收到相同的更新集合（全部 merge 消息投递完毕）后，状态必然等价/相同。**

固定实验设置（不要更改）：
- 副本数 **N ∈ {3, 4, 5}** 各跑一组。
- 每个副本先各自执行一段随机本地操作序列（总操作数 **~1e3–1e4**，混合各 CRDT 类型的 update；用确定随机种子保证可复现）。
- 然后按**全互联（full-mesh）**内存拓扑反复交换 `merge` 消息直到"安静"（再无状态变化）。
- 每个 N 用 **≥ 5 个不同种子**重复。

需要记录/报告的指标（每个 N）：
- **收敛正确率**：所有副本最终状态是否两两相同（应为 100%）；
- **收敛轮数**：从开始交换到全局安静所需的 merge 轮数（跨种子均值）。

把以下内容写到 `./summary_crdt_02_sec_convergence.md`：
1. 一张表：每个 N（3/4/5）下每种 CRDT 的收敛正确率与平均收敛轮数。
2. 结论要点：所有 CRDT 在所有种子下是否都达到 100% 收敛（SEC 成立）；收敛轮数是否随副本数 N 增加（约为全互联交换所需的 ~O(N) 或更少轮）。

---

[Judge]

Look at `./summary_crdt_02_sec_convergence.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 N∈{3,4,5} 下每种 CRDT（G-Counter/PN-Counter/G-Set/OR-Set/LWW-Register）的**收敛正确率**（应为 100%）与**平均收敛轮数**（基于 ≥5 种子），以表格呈现。
2. **所有 CRDT 在所有种子下均 100% 收敛**：全部副本最终状态两两相同（SEC 成立），且无需任何共识/协调——仅靠 join-merge 即可。
3. **收敛轮数随副本数 N 增加而上升**（全互联拓扑下需更多轮把状态传播到更多副本），给出 N=3/4/5 的具体轮数比较。

---

[Judge V2]

查阅 `./summary_crdt_02_sec_convergence.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准）：

1. 须给表：每 N∈{3,4,5}、每 CRDT 收敛正确率 100%、平均轮数 2.00（golden：100%+2.00；可接受：正确率 100%、轮数 ∈[2,3]）。（细化原 [Judge] 第 1 点）
2. 须给所有 CRDT 经 join-merge 达 100% SEC 无共识（golden：100%；可接受：≥99.9%）。（细化原 [Judge] 第 2 点）
3. **重写原 [Judge] 第 3 点**：原判"轮数随 N 增"在全连接下不成立——golden：轮数恒 2.00 不随 N；可接受：承认全连接 O(1) 不随 N 增、或指出仅受限 gossip 随 N 增即给分。（重写原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
