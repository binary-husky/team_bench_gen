[Agents]

读给定材料，做实验，写结论。

用 Python **进程内**实现同一计数器（仅 increment）的两种 CRDT 形态：
- **state-based（payload）G-Counter**：每次同步把**完整状态**（每副本计数向量，长度 = N）作为一条 merge 消息发送；接收方逐分量 max。
- **op-based（CmRDT）counter**：每次 `increment` 把**单个 increment 操作**（"副本 i 加 1"，定长小消息）经可靠因果广播发送；接收方累加。

研究目标：**对比 state-based 与 op-based CRDT 在消息代价上的权衡——随操作数增长，两者的"每条消息字节数"与"总传输字节数"如何变化。**

固定实验设置（不要更改）：
- 副本数 **N = 5**。
- 总 increment 操作数网格 **M ∈ {1e3, 5e3, 1e4, 5e4}**（均匀分摊到各副本）。
- state-based：约定每个副本每做一次本地 increment 后，向其余副本广播一次完整状态（payload）；统计这些广播的总字节数。
- op-based：每次本地 increment 广播一次定长 op 消息；统计总字节数。
- 字节计量：用 JSON 或等价定长编码的实际字节数（state 消息大小随 N 与计数增长，op 消息大小为常数）。
- 用 **≥ 3 个不同种子**重复（此处结果近似确定，种子用于分摊操作）。

需要记录/报告的指标：
- 每种 M 下，state-based 与 op-based 的**总传输字节数**，以及 **state-based 每条消息的平均字节数**（随 M 增长）、**op-based 每条消息字节数**（常数）。

把以下内容写到 `./summary_crdt_04_state_vs_op.md`：
1. 一张表：每个 M 下两种形态的总字节 + 每条消息字节。
2. 结论要点：op-based **每条消息 O(1)**、小而频繁；state-based **每条消息 O(N) 且随计数增长**、大而较少；随 M 增大，op-based 总字节按 O(M·const) 线性增长，state-based 增长更快（每条含增长的状态）——指出在"高频小更新"场景 op-based 更省带宽、"低频大状态"或需断点续传场景 state-based 更简单的权衡。

---

[Judge]

Look at `./summary_crdt_04_state_vs_op.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了每个 M 下 **state-based 与 op-based 的总传输字节数**及**每条消息平均字节数**，以表格呈现。
2. **op-based 每条消息 O(1)（常数小）**、**state-based 每条消息 O(N) 且随计数增长**——明确量化两者的每条消息字节差异（state-based 每条消息字节随 M 增大而增大，op-based 不变）。
3. 随 M 增大，**state-based 的总字节增长快于 op-based**（或反之，取决于编码/同步频率的设计，需与实测一致并解释）；并给出权衡结论：高频小更新宜用 op-based（省带宽），低频大状态/断点续传宜用 state-based（实现简单、可容忍消息丢失后用最新全量恢复）。

---

[Judge V2]

查阅 `./summary_crdt_04_state_vs_op.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准）：

1. 须给逐 M 总字节 + 逐消息字节表（golden：op 总 23k…1.15M、state 22.3k…1.47M、op 消息恒 23 B；可接受：同量级）。（细化原 [Judge] 第 1 点）
2. 须给 op 消息 O(1) 恒 23 B、state 消息 O(N) 随计数增（golden：op 23 B、state 22.28→29.45；可接受：op 恒定、state 随计数单调增）。（细化原 [Judge] 第 2 点）
3. 须给 state 总增长快于 op（golden：state/op 0.969→1.280；可接受：比随 M 单调增且 >1 at M=50k）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
