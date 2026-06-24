[Agents]

读给定材料，做实验，写结论。

用 Python **进程内**实现 state-based CRDT：**OR-Set**（每个 `add(x)` 附唯一 token；`remove(x)` 只移除"已观察到的 token"；`merge` = token 集合并）与 **PN-Counter**（`P`、`N` 两个 G-Counter，值 `= P − N`）。复现它们的并发语义。

研究目标：**验证 OR-Set 的 add-wins 语义与 PN-Counter 的 decrement 正确性——在跨副本的并发操作下，合并结果符合规范。**

固定实验设置（不要更改）：
- 副本数 **N = 3**。
- **(A) OR-Set add-wins**：构造大量并发场景，每场景中两个不同副本对同一元素 `x` **并发**执行 `add(x)` 与 `remove(x)`（用确定种子生成并发对，至少 **≥ 1000** 对）。merge 后检查 `x` 是否仍在集合中（add-wins：并发 add 与 remove，`x` 应保留）。
- **(B) PN-Counter decrement**：三副本交错执行 `increment`/`decrement`（总操作 **~1e3–1e4**，确定种子）；merge 后取 `值 = P − N`，与一个"单线程顺序回放同样操作序列"得到的精确值比对。
- 用 **≥ 5 个不同种子**重复。

需要记录/报告的指标：
- **(A) add-wins 正确率**：并发 `add+remove` 对中 `x` 保留的比例（应为 100%）；并对照：若误用"先到先得删除全部"语义，`x` 可能被错误移除。
- **(B) PN-Counter 值误差**：merge 后 `P−N` 与顺序回放精确值的差（应为 0）。

把以下内容写到 `./summary_crdt_05_addwins_pncounter.md`：
1. 表：(A) add-wins 正确率、(B) PN-Counter 值误差（跨种子）。
2. 结论要点：OR-Set 在并发 add+remove 下 **add-wins 100% 成立**（`x` 保留）；PN-Counter 的 `P−N` 在并发 increment/decrement 后与精确值**误差为 0**——二者共同验证 CRDT 的并发语义正确性。

---

[Judge]

Look at `./summary_crdt_05_addwins_pncounter.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了 **(A) OR-Set add-wins 正确率**（≥1000 个并发 add+remove 对中 `x` 保留的比例，应为 100%）与 **(B) PN-Counter 值误差**（merge 后 `P−N` 与顺序回放精确值之差，应为 0），基于 ≥5 种子，以表格呈现。
2. **OR-Set add-wins 100% 成立**：并发的 `add(x)` 与 `remove(x)`，`x` 始终保留（remove 只删已观察到的旧 token，删不掉并发新 add 的 token）——并说明若改用"删除全部"语义会破坏 add-wins。
3. **PN-Counter decrement 正确**：`P−N` 在跨副本并发 increment/decrement 后与精确顺序回放值**误差为 0**，验证 decrement 通过两个单调 G-Counter 的差被正确实现（呼应 _01 的结论）。
