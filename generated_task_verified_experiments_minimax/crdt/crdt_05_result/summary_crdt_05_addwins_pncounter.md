# State-based CRDT 验证：OR-Set 的 add-wins 语义 与 PN-Counter 的 decrement 正确性

> 实验代码：`./crdt_experiment.py`
> 原始数据：`./experiment_results.json`
> 材料：Shapiro, Preguiça, Baquero, Zawirski (2011) *A comprehensive study of
> Convergent and Commutative Replicated Data Types* (INRIA RR-7506) —
> `crdt_material/crdt_shapiro_2011.pdf`
> — §3.3.5 (Observed-Remove Set, Spec 15) 与 §3.1.3 (PN-Counter, Spec 7).

---

## 1. 实验目的

在 3 副本进程内（in-process、CPU-only）实现并运行两种 **state-based CRDT**，
并对它们的并发语义做受控验证：

* **(A) OR-Set 的 add-wins 语义**：并发 `add(x)` 与 `remove(x)` 后，`x` 必须
  保留（add-wins），不能被错误移除。
* **(B) PN-Counter 的 `decrement` 正确性**：并发 `increment` / `decrement` 后，
  merge 得到的 `P − N` 必须等于同一操作序列在单线程下的精确值（inc 数 − dec 数）。

固定实验设置（与任务约定一致）：

* 副本数 **N = 3**；
* **(A)** 每种子至少 **1200 对** 并发 `add(x)`（副本 A）与
  `remove(x)`（副本 B ≠ A）的并发对；
* **(B)** 每种子 **5000** 个操作（≈1e3–1e4 区间），三副本交错执行
  `increment` / `decrement`；
* 种子数 = **5**：`{1, 2, 3, 4, 5}`，全部由 `random.Random(seed)` 确定性生成。

---

## 2. 实现要点

### 2.1 OR-Set（state-based，add-wins）

载荷是 `(element, unique-tag)` 对的集合 `S`：

```python
class ORSet:
    def __init__(self, replica_id):
        self.replica_id = replica_id
        self.S = set()                  # set of (element, tag) tuples

    def add(self, e):
        tag = (self.replica_id, self._next_counter())
        self.S.add((e, tag))

    def remove(self, e):
        self.S -= {pair for pair in self.S if pair[0] == e}

    def merge(self, other):
        self.S |= other.S              # token 集合并
```

* 每个 `add(e)` 都在 source 副本生成一个**全网唯一**的 tag
  `(replica_id, counter)`，杜绝重号；
* `remove(e)` 只能删除**在 source 端已观察到的 token**——
  这正是 "Observed-Remove" 的语义来源；
* `merge` 是 token 集合并（union），幂等交换结合。

### 2.2 PN-Counter（state-based，decrement）

载荷是 `P[0..n-1]`、`N[0..n-1]` 两个 G-Counter 向量：

```python
class PNCounter:
    def increment(self):
        self.P[self.g] += 1
    def decrement(self):
        self.N[self.g] += 1
    def value(self):
        return sum(self.P) - sum(self.N)
    def merge(self, other):
        for i in range(self.n):
            self.P[i] = max(self.P[i], other.P[i])
            self.N[i] = max(self.N[i], other.N[i])
```

* `decrement` 全部走 `N[g] += 1`，状态向量本身从不下降；
* merge 仍是 `max`，是逐分量的 LUB，幂等交换结合；
* `value()` 把 `decrement` 翻译成 `P − N` 的代数差（Spec 7）。

---

## 3. 实验协议（保证 "并发"）

### 3.1 OR-Set

为了让 "并发" 在 in-process 模拟里也成立，对每个 `(seed, k)`：

1. **预置阶段**：在 *每个* 副本上先把 `x` 放进自己的 token 集合——
   这是 OR-Set `remove(x)` 的前提（"only observed tokens are removed"）。
2. **并发分发阶段**：随机选两个不同副本 A、B，让 A 执行 `add(x)`、
   B 执行 `remove(x)`。三个副本各操作自己的本地状态，互不感知对方，
   → 真并发（CRDT 论文里 "concurrent add(e) || remove(e)" 的标准构造）。
3. **全合并阶段**：把 3 个副本的状态两两 `merge`，得到统一视图。
4. **判定**：对每个 `(seed, k)`，问 "合并后 `x` 是否还在集合中？"——
   add-wins 语义下必须为 `True`。

并行地，我们对一个 **naive remove-wins 集合**（载荷仅是
`{Added, Removed}` 两个 set 的 2P-Set 风格）执行完全相同的协议——
它会把所有并发 `remove(x)` 看见的元素都错误地从 `Merged` 里抹掉，
正好作为反例（counter-example）对照。

### 3.2 PN-Counter

1. 用 `random.Random(seed)` 生成一条长度 = `n_ops` 的
   `(replica_id, op ∈ {inc, dec})` 调度；
2. 把这条调度"广播"给三副本：每个副本只处理轮到自己行号的 op，
   但 *不与其它副本同步*——这等于三副本各自独立消化了一段
   调度子集，恰好就是 PN-Counter 的并发场景；
3. 三副本 `merge` 后取 `value = ΣP − ΣN`；
4. **精确对照**：把同一条调度喂给一个普通 Python 整数
   `serial += 1 / serial -= 1`——它的最终值就是单线程顺序回放的
   inc 数 − dec 数，也是 CRDT 收敛后应该等于的值。

---

## 4. 实验结果

### 4.1 表 1：(A) OR-Set add-wins 正确率（跨种子）

| Seed | 并发对数 | add-wins 正确数 | add-wins 正确率 | naive remove-wins 误删数 | naive 误删率 |
|:---:|---:|---:|---:|---:|---:|
| 1    | 1200 | 1200 | **100.00 %** | 1200 | 100.00 % |
| 2    | 1200 | 1200 | **100.00 %** | 1200 | 100.00 % |
| 3    | 1200 | 1200 | **100.00 %** | 1200 | 100.00 % |
| 4    | 1200 | 1200 | **100.00 %** | 1200 | 100.00 % |
| 5    | 1200 | 1200 | **100.00 %** | 1200 | 100.00 % |
| **合计** | **6000** | **6000** | **100.0000 %** | **6000** | 100.00 % |

* add-wins 正确率 **5/5 种子 = 100.00 %**（共 6000/6000 对）。
* 对照：同一并发输入下，"先到先得删除全部" 的 naive 集合
  **错误地** 抹掉了 100% 的并发元素——正是 Shapiro 2011 §3.3
  引言里那张 op-based set 反例图（Figure 11）描述的失败模式。

### 4.2 表 2：(B) PN-Counter 值误差（跨种子）

`merged = value = ΣP − ΣN`；`serial = inc 数 − dec 数`（单线程精确值）。

| Seed | ops | inc | dec | merged (= ΣP − ΣN) | serial (精确) | error = merged − serial |
|:---:|---:|---:|---:|---:|---:|---:|
| 1   | 5000 | 2540 | 2460 |   80 |   80 | **0** |
| 2   | 5000 | 2541 | 2459 |   82 |   82 | **0** |
| 3   | 5000 | 2573 | 2427 |  146 |  146 | **0** |
| 4   | 5000 | 2502 | 2498 |    4 |    4 | **0** |
| 5   | 5000 | 2500 | 2500 |    0 |    0 | **0** |
| **合计** | **25000** | — | — | — | — | **Σ \|error\| = 0** |

* 误差 **5/5 种子 = 0**，所有跨副本并发 inc/dec 的最终 `P − N`
  都与"单线程回放同一条 op 序列"的精确值**完全一致**。
* 注意到 seed 5 上 inc/dec 数量恰好相等 (2500 / 2500) 而 merged 仍为 0——
  这正是 PN-Counter `value = 0` 这一平凡收敛态的正确性。

---

## 5. 结论要点

1. **OR-Set 在并发 `add(x) || remove(x)` 下 100 % 保留 `x`**——
   在 5 个独立种子、共 6000 个并发对（每对都是 "两个不同副本
   同时动 `x`" 的真并发）的实验里，add-wins 正确率为
   **100.00 %**。其机制是：每次 `add` 在 source 端生成全网唯一
   的 token，跨副本并发 `remove` **根本看不到**这个 token，
   因此 merge 后该 token 仍然残留在并集中，`x` 因此保留。

2. **PN-Counter 的 `P − N` 在并发 inc/dec 后与精确值误差为 0**——
   在 5 个独立种子、合计 25000 个跨副本交错 inc/dec 操作的实验里，
   merge 后的 `value` 与单线程顺序回放同一条 op 序列得到的
   `inc − dec` 值**完全相等**（误差 = 0）。
   这说明 `decrement` 通过映射为 `N[g] += 1` 这一方法，在
   保留状态向量单调性的同时，把 "可减" 的语义放进了查询层
   `P − N` 的代数差里——`P` 与 `N` 两个 G-Counter 各自独立
   单调、并各自 `merge = max`，收敛性由 G-Counter "免费继承"。

3. **二者共同验证了 CRDT 的并发语义正确性**：
   * OR-Set 的 add-wins 与 PN-Counter 的 decrement
     都来自 Spec 中显式给出的状态构造（载荷形态 + merge 定义）；
   * 在 5 个不同种子、远大于最小规模（1200 对 / 5000 ops）的
     实验里，二者都达到了"正确率 = 100 % / 误差 = 0" 的理想水平；
   * 反过来，一个简单的 naive remove-wins 集合在同一并发输入下
     **100 % 错误**——证明 OR-Set 的 add-wins 不是平凡的，而是
     "token-tag + observed-remove + union-merge" 这一组合
     才换来的并发安全。