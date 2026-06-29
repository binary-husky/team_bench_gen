# Space-Saving 算法：计数器总和恒等于流长度的严格论证与其误差上界

> 本文档仅通过逻辑推理完成，所有结论均来自 Metwally、Agrawal、El Abbadi (2005) 的论文 *Efficient Computation of Frequent and Top-k Elements in Data Streams*（特别是 Section 3 的 Space-Saving 算法描述与 Lemma 1–3 的证明）。

## 0. Space-Saving 算法回顾（必要前提）

Space-Saving 始终维护恰好 $m$（任务中称 $k$）个「（元素 ID, 计数器值）」槽位。设当前 $m$ 个计数器的值分别为 $\text{count}_1,\dots,\text{count}_m$。令

$$
N \;=\; \text{到目前为止已到达的流的总长度}。
$$

对每一个新到达的元素 $e$，算法按以下两条规则之一处理（参看图 1 的伪代码）：

- **Case A — $e$ 已经在监控集合中**：把 $e$ 对应的计数器 $+1$。这是唯一被改动的计数器。
- **Case B — $e$ 不在监控集合中**：找到当前所有计数器中**值最小**的那个（设其元素为 $e_m$，值为 $\min$）。把 $e_m$ 替换成 $e$，并把它的计数器置为 $\min+1$；同时把该元素的「上估误差」 $\varepsilon_m$ 记为 $\min$（$\varepsilon_m$ 表示 $e$ 真实出现次数与计数器值之差的上界）。

## 1. 命题 (1)：所有 $m$ 个计数器之和始终等于 $N$

**命题**。记 $S_t=\sum_{i=1}^{m}\text{count}_i^{(t)}$，其中 $t$ 是已处理流条数。则对所有 $t\geq 0$，$S_t = t$；当 $t=N$ 时即 $S=N$。

**证明（按 $t$ 归纳）**。

* 基础 $t=0$：流尚未到达，初始化时所有 $m$ 个计数器均为 $0$，故 $S_0=0=t$。

* 归纳步：设 $S_{t-1}=t-1$，处理第 $t$ 个到达的元素 $e$。分两种情况：
  - **Case A（$e$ 已被监控）**：仅 $e$ 的计数器 $+1$，故
    $$S_t = S_{t-1} + 1 = (t-1) + 1 = t.$$
  - **Case B（$e$ 未被监控）**：最小计数器 $\text{count}_m$ 被改成 $\text{count}_m+1$。这一步**没有**新增或删除槽位——是把 $e_m$ 的槽位原封不动地交给 $e$ 并把计数值加 $1$。因此
    $$S_t = S_{t-1} - \text{count}_m + (\text{count}_m+1) = S_{t-1} + 1 = t.$$

  两种情况下第 $t$ 条流都使 $S$ 严格增加 $1$，且 $S_0=0$，因此 $S_t = t$ 对所有 $t$ 成立。令 $t=N$ 即得
  $$\boxed{\;\sum_{i=1}^{m}\text{count}_i \;=\; N.\;}$$

**关键观察**：Case B 中「替换」是 *in-place* 的：算法从不删除空槽位，也从不引入额外槽位。它只把同一个计数器从 $e_m$ 手中转交给 $e$ 并把数值 $+1$。这一性质是总和守恒的根本原因。

> 该结论即论文 Lemma 1（"The length $N$ of the stream is equal to the sum of all the counters in the Stream-Summary data structure"）。

## 2. 命题 (2)：最小计数器 $\min$ 不可能超过 $N/m$

**命题**。记 $\min = \min_{1\leq i\leq m}\text{count}_i$。则 $\min \leq \dfrac{N}{m}$。

**证明**。对所有 $i$ 显然有 $\text{count}_i - \min \geq 0$。把 $m$ 个这样的非负项求和：

$$
0 \;\leq\; \sum_{i=1}^{m}(\text{count}_i - \min)
   \;=\; \underbrace{\sum_{i=1}^{m}\text{count}_i}_{=\,N\;\text{（由命题 1）}} \;-\; m\cdot\min
   \;=\; N - m\cdot\min.
$$

移项即得 $m\cdot\min \leq N$，亦即

$$
\boxed{\;\min \;\leq\; \dfrac{N}{m} \;=\; \dfrac{N}{k}.\;}\quad\blacksquare
$$

**注（$m$ 个槽位尚未全部被占满的情形）**：若监控集合中的不同元素数 $<m$，则必有若干计数器仍为 $0$，于是 $\min=0\leq N/m$ 自动成立，无需讨论；命题对任何状态均正确。

> 这就是论文 Lemma 2（"the minimum counter value, min, is no greater than $\lfloor N/m\rfloor$"）的严格形式。

## 3. 命题 (3)：对「任意被监控元素频率的高估误差」的确定性上界

**3.1 上估误差 $\varepsilon_i$ 的定义**。
对监控集合中排第 $i$ 位（按计数器值升序）的元素 $e_i$，令 $f_i$ 为其计数器值（估计频率），$F_i$ 为其在流中**真实**出现次数。每次把一个新元素 $e$ 替换掉最小计数器 $e_m$ 时，$e$ 的计数器被设为「旧 $\min +1$」，同时记录其上估误差为「旧 $\min$」。

对任何已被监控的元素 $e_i$，其上估误差 $\varepsilon_i$ 始终**等于**它被加入监控集合时那次替换的「旧 $\min$」（参看论文 Lemma 3 证明中的赋值规则 $\varepsilon_m := \text{min}$）。

**3.2 上估误差的单调不增性**。
设 $e_i$ 在 $t_0$ 时刻被加入监控集合（通过一次替换），当时旧 $\min$ 记为 $m_0$。从 $t_0$ 起：
- 此后若 $e_i$ 又被流命中（Case A），其计数器 $\text{count}_i$ 增加，但**没有人重新设置 $\varepsilon_i$**。
- 此后若发生其它元素的替换（Case B），**新的 $\min$ 只会更小或不变**（因为每次替换都把当前最小计数器加 $1$，而 $e_i$ 计数器只增不减，所以 $e_i$ 不再可能是最小者；最小者只会在其它槽位之间产生并随替换单调上升直到 $e_i$ 之下没有更小者——注意：每次替换都把一个最小计数器从 $\min$ 变成 $\min+1$，而 $e_i$ 在加入后不久便已 $\geq \min$，所以一旦被替换，$e_i$ 此后再也不会被选为被替换者。详细地：由于每次替换都把当前 $\min$ 槽位增 $1$，而 $\min$ 在替换发生时是全局最小，所以 $\min$ 单调不降；$e_i$ 的计数器在加入时为 $m_0+1$ 且仅增不减，故 $e_i$ 计数器 $\geq m_0+1 \geq \min$，于是 $e_i$ 永远不可能再次成为被替换者。）

因此 $e_i$ 的上估误差 $\varepsilon_i$ 在加入监控集合之后**保持不变**，并始终满足

$$
\varepsilon_i \;\leq\; \text{（加入后任意时刻的全局)}\;\min
\;\leq\; \dfrac{N}{m} \;=\; \dfrac{N}{k}.
$$

**3.3 频率估计的确定性上界**。
对任何被监控的元素 $e_i$，其真实频率 $F_i$ 满足

$$
F_i \;\leq\; f_i \;=\; \text{count}_i \;\leq\; F_i + \varepsilon_i \;\leq\; F_i + \dfrac{N}{k}.
$$

故 $e_i$ 的估计频率 $f_i$ 相对真实频率 $F_i$ 的**高估误差**为

$$
\boxed{\;f_i - F_i \;\leq\; \varepsilon_i \;\leq\; \dfrac{N}{k}.\;}\quad\blacksquare
$$

> 该结论即论文 Lemma 3（"for any element $e_i$ in the Stream-Summary, $0\leq \varepsilon_i \leq \min$, $f_i = \text{count}_i \leq f_i + \min$"）和 Theorem 3（"Assuming no specific data distribution, Space-Saving uses a number of counters of $\min(\lceil|A|/\epsilon\rceil,\dots)$ to find all frequent elements with error $\epsilon$"，把 $\epsilon = N/k$ 代入即得 $k\geq N/\epsilon$）的结合。

## 4. 三条命题的逻辑链（一句话总结）

> (1) 每条流到达都让所有 $m$ 个计数器之和**严格**增加 $1$（不论 Case A 还是 Case B，Case B 是 in-place 替换），因此总和恒等于流长度 $N$；
> (2) 由总和 $=N$ 与 $m$ 个非负项的算术-几何平均关系立得 $\min \leq N/m$；
> (3) 任意被监控元素 $e_i$ 的高估误差 $\varepsilon_i$ 等于其被替换入监控集合时那一刻的 $\min$ 值，并且此后 $\min$ 只会上升、$e_i$ 永不再被替换，故 $\varepsilon_i$ 单调不增，从而 $f_i \leq F_i + N/k$。

这就是 Space-Saving 算法在最坏情况下依然能给出**确定性**（非概率、非期望）误差上界 $\varepsilon \leq N/k$ 的本质原因——它是直接由「总和守恒 + 最小值与平均值的偏序关系 + 替换在 in-place 单调更新」这三条性质推得的，不依赖任何数据分布假设。

## 5. 与论文的对应关系（便于核对）

| 任务中的命题 | 论文对应 |
|---|---|
| (1) 计数器总和 $=N$ | **Lemma 1** (§3.2) |
| (2) $\min\leq N/m$ | **Lemma 2**（由 Lemma 1 改写为式 (1) 后推出；§3.2）|
| (3) 高估误差 $\leq N/k$ | **Lemma 3**（$0\leq\varepsilon_i\leq\min$）+ **Theorem 3**（一般分布下 $m$ 取 $\lceil N/\epsilon\rceil$ 即保证 $\epsilon\leq N/m$；§4.1.1）|
| 误差确定性（无概率） | **Theorem 4 的下半段**（下界反例证明中说明：本文所给上界对所有输入流均成立，与 Sticky Sampling/CountSketch 等概率算法形成对比）|

---

**结论**：Space-Saving 算法在任意数据分布、任意流长度 $N$、任意维护 $k$ 个计数器的设置下，对任何被监控元素 $e_i$，其频率估计的过估计误差均满足

$$
f_i - F_i \;\leq\; \dfrac{N}{k},
$$

这是一个**最坏情况确定性**上界，不依赖概率论证、也不依赖 Zipf 等特定分布假设。
