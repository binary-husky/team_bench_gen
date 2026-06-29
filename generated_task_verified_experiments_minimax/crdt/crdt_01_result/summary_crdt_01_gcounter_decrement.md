# 为什么 state-based G-Counter 在原理上无法支持 `decrement`

> 本文档不进行任何代码实验，只依据 Shapiro 等人 2011 年综述
> *"A comprehensive study of Convergent and Commutative Replicated Data Types"*
> (RR-7506) §2.3.1 (CvRDT / semilattice / LUB / Proposition 2.1) 与
> §3.1.2–§3.1.3 (G-Counter / PN-Counter) 的定义，作纯逻辑推理。

---

## 1. State-based CRDT 收敛的两个结构前提

State-based CRDT（即 CvRDT）的全部"无协调收敛"保证来自两个简单的结构性条件
（见 Shapiro 2011 §2.3.1：Definition 2.4 LUB、Definition 2.5 Join Semilattice、
Definition 2.5 后关于 CvRDT 的概括、Proposition 2.1）：

> **前提 (a) — 单调性 (Monotonicity of updates)：**
> 状态集 $S$ 配上偏序 $\leq_v$，且每次本地 `update` 之后的新状态 $s'$ 都满足
> $s \leq_v s'$——即状态只能沿偏序"上移"，向 LUB 增长，永不回退。
>
> **前提 (b) — `merge` 是 join / LUB：**
> `merge(x, y) = x ⊔_v y`，其中 $\sqcup_v$ 满足
> *交换* $x ⊔ y = y ⊔ x$、*结合* $(x ⊔ y) ⊔ z = x ⊔ (y ⊔ z)$、
> *幂等* $x ⊔ x = x$。$S$ 在 $\leq_v$ 下构成 join semilattice。

### 为什么 (a) + (b) ⇒ SEC（强最终一致性），无需任何共识/协调

Proposition 2.1 给出这条证明的骨架；这里用语义复述一遍：

* 设任意两副本 $x_i, x_j$，并设它们在某时已交换过状态、之后又分别
  执行了若干本地更新——记 $x_i' = \text{merge}(x_i, x_j)$，
  $x_j' = \text{merge}(x_j, x_i)$。
* 由 (b) 的**幂等**：merge 与自身合并结果不变；由 (b) 的**交换**：
  $x_i ⊔ x_j = x_j ⊔ x_i$；再由 (b) 的**结合**：
  $(x_i ⊔ x_j) ⊔ x_i = x_i ⊔ (x_j ⊔ x_i) = x_i ⊔ x_i = x_i$。
  这说明任意两副本的"先 merge 再各自演化"是同一条偏序链。
* 由 (a)：本地更新只是把状态沿偏序上移，所以"演化"在偏序上单调——
  不会出现 $x_i ⊔ x_j$ 又被某个更新拉回到 $x_i$ 以下。
* 结论：当且仅当两副本最终交换到同一组初始 / 更新值时，
  它们的 merge 结果一定相等（都是这些值的 LUB），与消息顺序、
  是否丢失重发、是否并发都无关。
  因此**不需要任何形式的共识、原子广播、共识编号、Paxos/Raft**。
  整个收敛论证只用了 join semilattice 的代数律——这就是
  "CRDT 用纯局部代数学换掉了分布式共识"的核心。

---

## 2. `decrement` 与单调性的冲突

### (i) 在偏序 $\leq_v$ 下，`decrement` 是下降，违反前提 (a)

G-Counter 的状态空间是 $S = \mathbb{N}^n$（$n$ 个副本，每副本一个非负整数计数器），
偏序 $\leq_v$ 就是**逐分量 $\leq$**（Spec 6：`compare(X,Y) := ∀i. X[i] ≤ Y[i]`），
`value(X) = Σ_i X[i]`。"单调性"在这里就是：

> 每一次本地更新后的状态 $s'$ 都满足 $s \leq_v s'$——即每个分量都只能升不能降。

`decrement` 想把某分量从 $c$ 改成 $c-1$。但 $c-1 \leq c$ 不成立、
$c \leq c-1$ 也不成立——$s$ 与 $s'$ 在逐分量偏序下**不可比 (incomparable)**，
而不是满足 $s \leq_v s'$。所以 `decrement` 直接破坏了前提 (a)：
状态不再是沿偏序上移的，semilattice 的"单调更新 → LUB 收敛"链路被切断。

直观地讲：如果更新可以向下走，那么"两个副本都收到同样的更新集"
就不再等价于"两个副本都能算出相同的最终状态"——因为同样的
更新序列在 A 处先增后减得到 $x$，在 B 处先减后增可能得到完全不同的
$y$（而 $x, y$ 在 $\leq_v$ 下又无法相互比较），从而 CvRDT 的收敛证明
彻底崩塌。

### (ii) 更根本地：`merge = max` 这个幂等 join 无法传播"下降"

这一点比 (i) 更具破坏性——即便 (i) 的"单调性"条件以某种方式被绕过，
`merge = max` 自身也会把 `decrement` 永久吞掉，使得状态根本无法
离开已经到达的最大值。Shapiro 2011 §3.1.3 正是这么说的：

> *"It is not straightforward to support decrement with the previous
> representation, because this operation would violate monotonicity
> of the semilattice. Furthermore, since merge is a max operation,
> decrement would have no effect."*

具体推理：

* 设某副本 $x$ 已 merge 过分量 $i$ 的值 $c$，即 $x[i] = c$。
* 现在另一副本 $y$ 执行 `decrement`：$y[i] = c-1$，并把这个状态传播给 $x$。
* $x$ 收到后做 $x ⊔ y$：`max(x[i], y[i]) = max(c, c-1) = c`。
  下降**被 `max` 直接吞掉**。
* 反过来也一样：即便 $x$ 自己执行 `decrement` 把分量降到 $c-1$，
  只要它之后又与一个分量仍为 $c$ 的副本 merge，结果仍然是 $c$——
  任何一个曾经 merge 到过 $c$ 的副本都会把这个下降"否决"掉。
* 这同时破坏了 LUB 的**幂等性意义**：幂等本意是"重放同一信息无副作用"，
  但在带 decrement 的状态下，"一个分量被某副本拉低"与
  "另一个副本保留更高的分量"是两类无法被 LUB 同时吸收的信息，
  join 没有办法把它们折成一个共同的目标状态。

因此，对 state-based G-Counter 增加 `decrement` 在原理上有**双重失败**：
不仅更新本身违反单调性，更致命的是 `merge = max` 这种 join
**结构性地无法把"减小"这一信息传出去**——任何到达过的最大值都成了天花板，
天花板之下的所有差异都将被 `max` 抹平。

---

## 3. PN-Counter 如何"绕开"该限制

Shapiro 2011 §3.1.3 给出 PN-Counter（Spec 7），其精妙之处在于：
**它没有把 decrement 直接放进 G-Counter 里，而是把它从状态里搬到查询层**。

### 状态结构

* 载荷是**两个**向量：$P \in \mathbb{N}^n$（记所有 `increment`）与
  $N \in \mathbb{N}^n$（记所有 `decrement`）。
* `value(P, N) := Σ_i P[i] − Σ_i N[i]`。
* `compare((P,N), (P',N')) := (∀i. P[i] ≤ P'[i]) ∧ (∀i. N[i] ≤ N'[i])`，
  即**逐对逐分量**的偏序（两个 semilattice 的 product 偏序）。
* `merge((P,N), (P',N')) := (逐分量 max P, 逐分量 max N)`——两个分量各自做 max，
  整个 merge 还是一个 join/LUB（每个分量幂等交换结合，整个逐对 max 自然也幂等交换结合）。

### `increment` / `decrement` 的新定义

* `increment` at replica $g$：$P[g] := P[g] + 1$，$N$ 不动。
* `decrement` at replica $g$：$N[g] := N[g] + 1$，$P$ 不动。

关键观察：

1. **$P$ 和 $N$ 各自都是一个 G-Counter，各自满足前提 (a)+(b)。**
   它们内部永远只做"对某个分量 $+1$"——纯单调、纯上移，
   merge = max 在 $P$、$N$ 各自的 semilattice 上都安全、合法。
2. **decrement 变成了"$N$ 的一个 increment"**——也就是说，
   真正承担"可减"语义的不是状态值的下降，而是状态向量的第二个分量
   $N$ 的上升。$P$、$N$ 两个分量依旧各自单调、依旧 join 收敛。
3. **"可减"是被读出来的**：用户看到的最终值 $P - N$ 是一个**导出量**，
   在 query 时计算——读出层做代数减法，与 $P$、$N$ 内部单调性无关。
   即使 $(P - N)$ 这个数字下降，状态向量 $(P, N)$ 本身从不会下降，
   偏序从不违反，merge 永不吞掉信息。

于是 PN-Counter 的状态收敛由 G-Counter 的收敛性"免费继承"而来——
前提 (a)+(b) 对 $(P, N)$ 整体成立（product semilattice），所以所有副本
最终会到达相同的 $(P, N)$，从而 $\Sigma P - \Sigma N$ 也自动一致，
SEC 重新成立，依然无需任何共识/协调。

---

## 4. 一句话结论

> **G-Counter 不能 `decrement` 的根本原因不是"加一个 API 难写"，
> 而是 state-based CRDT 收敛性的两条结构前提（更新单调 + `merge` 为幂等 join）
> 与"状态值可下降"在数学上互斥**——单点降值既破坏偏序的单调性，
> 更会被作为 join 的 `max` 永久吞掉；**PN-Counter 能做到 decrement，是因为
> 它把"可减"翻译成"两个永远只升的 G-Counter 的代数差"——
> 让"减"留在读出层、把"加"留给单调状态层，
> 从而绕过了 `merge = max` 无法传播下降这一原理性障碍。**