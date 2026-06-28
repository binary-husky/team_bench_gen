# CRDT 并发语义验证：OR-Set add-wins 与 PN-Counter decrement

实现依据：Shapiro et al., *A comprehensive study of CRDTs* (INRIA RR n°7506, 2011) —
Spec. 7 (state-based PN-Counter) 与 Spec. 15 (OR-Set，论文指出 state-based 可基于 U-Set，
即 (元素, 唯一 tag) 对的并集合并)。全程 Python 进程内实现，CPU-only，确定性种子。

固定设置：副本数 N = 3；每种子 (A) 2000 对并发 add+remove，(B) 5000 次交错 inc/dec；共 7 个不同种子。

## (A) OR-Set add-wins 正确率

| seed | 并发对数 | OR-Set 保留 x 数 | OR-Set 正确率 | 2P-Set(对照) 保留 x 数 | 2P-Set 保留率 |
|----:|----:|----:|----:|----:|----:|
| 1 | 2000 | 2000 | 100.00% | 0 | 0.00% |
| 2 | 2000 | 2000 | 100.00% | 0 | 0.00% |
| 3 | 2000 | 2000 | 100.00% | 0 | 0.00% |
| 4 | 2000 | 2000 | 100.00% | 0 | 0.00% |
| 5 | 2000 | 2000 | 100.00% | 0 | 0.00% |
| 7 | 2000 | 2000 | 100.00% | 0 | 0.00% |
| 11 | 2000 | 2000 | 100.00% | 0 | 0.00% |
| **合计** | 14000 | 14000 | **100.00%** | 0 | 0.00% |

对照说明：2P-Set（remove-wins / “删除即 tombstone 全部”语义）在并发 remove 下 x 被移除，保留率 ~0%，正是“误用先到先得删除全部语义时 x 可能被错误移除”的体现。

## (B) PN-Counter 值误差（merge 后 P−N vs 顺序回放精确值）

| seed | 操作数 | 分布式 P−N | 顺序回放精确值 | 误差 |
|----:|----:|----:|----:|----:|
| 1 | 5000 | -20 | -20 | 0 |
| 2 | 5000 | 62 | 62 | 0 |
| 3 | 5000 | 30 | 30 | 0 |
| 4 | 5000 | 80 | 80 | 0 |
| 5 | 5000 | -8 | -8 | 0 |
| 7 | 5000 | -8 | -8 | 0 |
| 11 | 5000 | 10 | 10 | 0 |

跨种子最大 |误差| = **0**。

## 结论要点

- **OR-Set add-wins 100% 成立**：跨 7 个种子、共 14000 对并发 add+remove，合并后 x 保留比例为 **100.00%**。机理：每个 `add(x)` 附唯一 token，`remove(x)` 只移除源副本“已观察到的” token；并发 add 的新 token 不被并发 remove 观察到，故在 union 合并后存活 → add 竞胜。对照的 2P-Set（remove-wins）保留率仅 0.00%，印证 token 观察机制是 add-wins 的关键。
- 顺序因果正确性校验：当 remove 因果后发生于 add（已同步观察），OR-Set 正确移除 x（结果：removed (正确)），说明 add-wins 仅作用于 *并发* 场景，不破坏顺序语义。
- **PN-Counter decrement 误差为 0**：跨 7 个种子、每种子 5000 次交错 increment/decrement（含运行中随机两两 merge），最终全合并 `值 = ΣP − ΣN` 与单线程顺序回放同一操作序列所得精确值之差，最大 |误差| = **0**。因为 P、N 各为按副本分量的 G-Counter（merge 取逐分量 max，单调），inc/dec 各自累加本副本分量，故无论 merge 何时发生，最终 ΣP−ΣN 恒等于 (总 increment − 总 decrement)，与顺序结果一致。
- 二者共同验证：state-based CRDT（OR-Set 与 PN-Counter）在跨副本并发操作下，合并结果符合规范，并发语义正确。
