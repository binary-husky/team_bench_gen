# 为什么 G-Counter 不能 decrement，而 PN-Counter 能

> 纯逻辑推理，无任何代码实验。论证依据为给定材料 Shapiro et al., *A comprehensive study of Convergent and Commutative Replicated Data Types* (RR-7506, 2011)，主要 §2.3.1（CvRDT 形式化）、§3.1.2（G-Counter, Spec 6）、§3.1.3（PN-Counter, Spec 7）。材料把 G-Counter 与 PN-Counter 都给出了，但只用一句话点到"decrement 违反单调性、且 max 下无效"（§3.1.3），**没有**把下面这条完整论证作为结论写出；本文将其补全。

---

## 0. 记号（来自 §3.1.2 / Spec 6）

- G-Counter 状态：副本计数向量 `v ∈ ℕⁿ`，`v[i]` 是副本 `i` 的本地计数。
- 偏序：`X ≤ Y ⇔ ∀i: X.P[i] ≤ Y.P[i]`（逐分量整数序）。
- `merge(X,Y)`：逐分量 `max`，即偏序下的 join / LUB `⊔`。
- `increment`：`P[myID] := P[myID] + 1`。
- 查询值 `value = Σᵢ P[i]`。

---

## 1. state-based CRDT 收敛的两个结构前提

### 前提 (a)：更新必须单调 —— 沿偏序只能上移、永不回退

CvRDT 的 payload 取值于一个 join-semilattice `(S, ≤)`；每个 update 操作 `f` 必须满足
`x ≤ f(x)`（更新后状态 ≥ 更新前状态）。这就是材料所谓的 *monotonic semilattice* 中"monotonic"那一半（§2.3.1："the payload value after an update is greater than or equal to the one before"）。

### 前提 (b)：merge 必须是 join/LUB —— 交换 + 结合 + 幂等

`merge(x,y) = x ⊔ y`，而由 LUB 的定义（Def 2.4）直接推出 `⊔` 满足：
- 交换 `x ⊔ y = y ⊔ x`；
- 幂等 `x ⊔ x = x`；
- 结合 `(x ⊔ y) ⊔ z = x ⊔ (y ⊔ z)`。

### 为什么这两条 ⇒ 强最终一致性（SEC）且无需任何共识/协调

**核心事实**：在 monotonic semilattice 中，一个副本在因果历史 `C`（它执行过的所有 update 与 merge 的集合）下的状态，恰好等于

```
state(C) = ⊔_{f ∈ C} f(init)          // 它"见过的全部更新效果"的 LUB
```

理由：(a) 单调性保证每个 `f` 是一次上移，其效果可表为 `init` 之上的一个元素；(b) `merge = ⊔` 保证累加这些效果就是逐次取 join，最终落到全体的 LUB。

而 LUB 的三条性质（Def 2.4 推论）恰好把"收敛条件"逐一消解：
- **交换 + 结合** ⇒ `state(C)` 只依赖于**集合** `C`，与更新到达/执行的**顺序**无关；
- **幂等** ⇒ `state(C)` 只依赖于集合，与每条更新到达的**次数**无关（重复消息无害）。

于是得到 SEC 的 safety（Def 2.3）：

```
C(xᵢ) = C(xⱼ)  ⟹  state(xᵢ) = state(xⱼ)  ⟹  所有 query 返回相同值
```

liveness 由"信道最终投递"假设保证。这正是材料 Proposition 2.1 的证明骨架：`C(xᵢ) ∪ C(xⱼ) = C(xⱼ) ∪ C(xᵢ)`，且由 LUB 交换律 `xᵢ ⊔ xⱼ = xⱼ ⊔ xᵢ`。

**为何无需共识**：收敛只要求每个副本最终**以任意顺序、任意次数**收到同样的更新集合即可，它不需要：
- **全序**——交换律吸收任意到达顺序；
- **去重**——幂等吸收重复；
- **两阶段提交 / quorum / leader**——每个副本本地 `merge` 即可，互相 gossip 状态。

共识（对操作全序达成一致）只有在操作**不可交换**、或要求强一致/线性一致性时才不可避免。CvRDT 把收敛建立在"可交换 + 幂等 + 结合的 join"之上，从结构上绕开了共识；这也是它能在网络分区下仍最终收敛的根本原因。

> 一句话：(a) 单调性让"最新值"可定义为偏序上的最大值（即 LUB，更新只增不减、信息不丢）；(b) join 让任意副本都能本地、无序、无需去重地算出这个 LUB。两条合起来才同时成立 SEC 与"无需协调"，缺一不可。

---

## 2. decrement 与单调性冲突

工程师想新增 `decrement`：把某分量从 `c` 降到 `c − 1`。

### (i) 直接违反前提 (a)：这是一次下降

在逐分量偏序 `≤` 下，`c − 1 ≤ c` 且 `c ≰ c − 1`（严格地 `c − 1 < c`）。于是更新前 `x_before = c`、更新后 `x_after = c − 1` 满足 `x_after < x_before`，即 `x_after ≤ x_before` 但 `x_before ≰ x_after`——**方向正好与前提 (a) 要求的 `x_before ≤ x_after` 相反**。decrement 是沿偏序的**下移**，结构性地破坏 monotonic semilattice。这是第一层、也是最表层的不可行。

### (ii) 更根本：`merge = max`（幂等 join）无法传播下降

即便暂时无视 (i)、强行让某副本本地把分量从 `c` 减到 `c − 1`，这条下降也**永远传播不出去**，会被 `max` 吞掉。分两层证明：

**局部层（自吞）**：一旦某状态里出现过分量值 `c`，`max(..., c) = c`（幂等：`max(c, c) = c`）。副本 `i` 自己历史上（或别的副本）已持过 `c`；当 `i` 下一轮 `merge` 时 `max(c, c − 1) = c`——本地刚做的 −1 立刻被自己持过的旧值 `c` 抹平。

**全局层（永久丢失）**：假设 `c` 已通过 merge 扩散到若干副本。则无论别的副本如何自减、何时再 merge，结果恒为 `max(c, c − 1) = c`。该分量被**钉死**在 `c`：**不存在任何 "decrement + merge" 的序列能把它降到 `c` 以下**。

这触及最深层的原因：

> **join / LUB 关于每个自变量单调非减**：按定义 `m = x ⊔ y` 必满足 `x ≤ m ∧ y ≤ m`。因此 `⊔` 永远只能产出"上界"，**永远无法产出严格小于某个已有状态的值**。而 decrement 恰恰要求产出一个**小于**已持有值的结果。故 decrement 在 join-semilattice 框架内**不可表达**——这不是工程实现难，而是数学结构上不存在这样的更新。

（反证：若想让 merge 能下降就不能用 `max`；改用 `min` 能传播下降却再也无法传播 increment。单一标量上无法既用 `max` 又用 `min`，因此无法兼顾增减——这正是必须引入第二个量的根由。）

> 材料 §3.1.3 仅一句话点到此要害："It is not straightforward to support decrement with the previous representation, because this operation would violate monotonicity of the semilattice. Furthermore, since merge is a max operation, decrement would have no effect." 上面 (i)(ii) 即把这两句展开为完整论证链：表层是单调性被破坏，深层是 max 的"单调非减 + 幂等"使下降永久不可传播。

---

## 3. PN-Counter 如何绕开该限制

PN-Counter（Spec 7）用**两个** G-Counter：

- `P`：计所有 increment，每次 `increment` 做 `P[myID] += 1`；
- `N`：计所有 decrement，每次 `decrement` 做 `N[myID] += 1`；
- 查询值 `value = Σᵢ P[i] − Σᵢ N[i]`。

**关键设计**：decrement **不是**去减小 `P`，而是去**增大 `N`**。`N[myID] += 1` 是一次地地道道的 **+1 上移**，完全满足前提 (a)。第 2 节里"下降无法传播"的矛盾，因为根本没有下降发生而被绕开。

逐条核对两个前提对 `P`、`N` 仍然成立：

- **单调 (a)**：`P`、`N` 各自只做 +1，每个分量只增不减 ⇒ 二者各自都是合法的 monotonic semilattice；
- **join (b)**：`merge` 对 `P`、`N` 各自逐分量取 `max` ⇒ 各自的 `⊔` 仍是 idempotent/commutative/associative。乘积 `(P, N)` 配以"逐分量合取"偏序（Spec 7 第 12 行）与逐分量 `max`（第 14–15 行），是两个 semilattice 的**乘积 semilattice**——任意两点的 LUB 仍存在（分量分别取 LUB）——故 PN-Counter 整体仍是合法 CvRDT。（材料原话："its partial order is the conjunction of the corresponding partial orders, and merge merges the two vectors. Proving that this is a CRDT is left to the reader."）

**为什么这样能"减"而仍 SEC、仍无需共识**：收敛所依赖的抽象状态是**二元组 `(P, N)`**，而非标量值。两个副本因果历史相同 ⇒ `P` 相等（同样的 increment 集合）且 `N` 相等（同样的 decrement 集合）⇒ `(P, N)` 相等 ⇒ `value = P − N` 相等。**减法只发生在 query 时**，是两个单调增量的**代数差**，根本不参与状态格的演化——格里的每一步（无论 +1 到 `P` 还是 +1 到 `N`）都是严格上移，单调性与 join 收敛从未被破坏，gossip + max 机制照常工作。

PN-Counter 的精髓：**把"负方向"重新编码为"另一个独立正量的增长"**。于是"减计数 = 加 N"，仍全程单调、仍用 `max` 收敛、仍无需共识；可见值之所以能下降，是因为差 `P − N` 可随 `N` 增长而变小，而非任何分量在格中下移。

---

## 结论

**G-Counter 不能 decrement**：它的状态格中合法的移动只有"上移"（单调性所迫），且 `merge = max` 这个幂等 join 对每个自变量单调非减、永远只能给出上界、永远吞掉下降。decrement 是一次下移——既被单调性禁止，又会被 `max` 永久吞噬——因而在该结构内**原理上不可表达**。

**PN-Counter 能**：它不试图让任何分量下降，而是把 decrement 编码成对第二个 G-Counter `N` 的 +1（单调上移），让 `P`、`N` 各自、以及乘积 `(P, N)` 全程满足单调 + join 收敛，把减法推迟到 query 时的代数差 `P − N`。单调性从未被违反，却实现了可减计数。

> 一句话：**减法在"单标量 monotonic semilattice"里无处安放；PN-Counter 通过把它移到"两个单调增量之差"的查询层，绕开了这一结构限制。**
