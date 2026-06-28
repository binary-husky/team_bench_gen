# Count-Min Sketch 点查询「单边误差（只高估、不低估）」的结构性证明

> 本文**不借助任何概率误差界**（不涉及 Markov / 期望 / 两两独立的好性质），只从「更新规则（每行加非负计数）+ 查询规则（取 $d$ 行最小值）」的**结构**出发，严格证明点查询估计 $\hat a_i$ 恒有 $\hat a_i \ge a_i$，并给出「取 min 的保号性」与「只增流下单调不减」两条推论。
>
> 论文（Cormode & Muthukrishnan, *An Improved Data Stream Summary: The Count-Min Sketch and its Applications*）在 Theorem 1 的证明里把这件事当作显然事实一句话带过——
> *"By construction, $\text{count}[j,h_j(i)] = a_i + X_{i,j}$. So, **clearly**, $\min_j \text{count}[j,h_j(i)] \ge a_i$."*
> 本文把这句 "clearly" 展开成一条完整的、确定性的证明链及其推论。

---

## 0. 记号与设定（与论文一致）

- 隐式向量 $a = (a_1,\ldots,a_n)$，初值为 $0$。数据流是一串更新 $(i_t, c_t)$，含义为 $a_{i_t} \leftarrow a_{i_t} + c_t$。**本题限定 $c_t \ge 0$**（cash-register / 只增模型；论文称作 non-negative case），因此每个真实频率 $a_i = \sum_{t:\,i_t=i} c_t \ge 0$。
- CM sketch：$d$ 行、每行 $w$ 个计数器，$d$ 个哈希函数 $h_1,\ldots,h_d:\{1,\ldots,n\}\to\{1,\ldots,w\}$，所有计数器初值为 $0$。
- **更新** $(i,c)$：$\forall\, j\in\{1,\ldots,d\}$，$\;C[j,h_j(i)] \leftarrow C[j,h_j(i)] + c$。
- **点查询**：$\hat a_i = \min_{j=1}^{d}\, C[j,h_j(i)]$。

目标：证明对**任意数据、任意哈希函数**恒有 $\hat a_i \ge a_i$。

---

## 1. 单行视角：每个计数器 $= a_i\;+\;$（非负碰撞噪声）

固定任意一行 $j$、任意 item $i$，考察格 $C[j,h_j(i)]$ 里到底累加了哪些更新。

**结构事实**：一条对 item $i'$ 的更新 $(i',c)$，在第 $j$ 行只会把 $c$ 加到格 $C[j,h_j(i')]$ 上。因此 $C[j,h_j(i)]$ 这一格**恰好**收下所有满足 $h_j(i')=h_j(i)$ 的 item 的更新。形式上：

$$
C[j,h_j(i)] \;=\; \sum_{t=1}^{T} \mathbf 1\!\big[h_j(i_t)=h_j(i)\big]\cdot c_t
\;=\; \sum_{i'\,:\,h_j(i')=h_j(i)} \!\! a_{i'}.
$$

（第二个等号：按 item 把更新分组求和，$\sum_{t:i_t=i'} c_t = a_{i'}$。**全式只用「更新是累加的」这一结构性事实**，无任何概率。）

注意 $i$ 自己恒满足 $h_j(i)=h_j(i)$，故 $i$ 必然出现在右端求和指标中。把它单独拆出：

$$
C[j,h_j(i)] \;=\; a_i \;+\!\! \sum_{\substack{i'\ne i\\ h_j(i')=h_j(i)}} \!\! a_{i'}.
$$

第二项是「**碰撞噪声**」，记作（论文里对应的随机变量为 $X_{i,j}$，由指示量 $I_{i,j,k}=\mathbf 1[(i\ne k)\wedge(h_j(i)=h_j(k))]$ 之和构成）

$$
\mathrm{noise}_j(i) \;=\!\!\sum_{\substack{i'\ne i\\ h_j(i')=h_j(i)}} \!\! a_{i'} \;\ge\; 0,
$$

非负是因为每条 $c_t\ge 0$，从而每个 $a_{i'}\ge 0$。于是

$$
\boxed{\;C[j,h_j(i)] \;=\; a_i + \mathrm{noise}_j(i) \;\ge\; a_i.\;}
$$

**为什么对每一行都成立、且与哈希好坏无关**：$i$ 永远命中自己所在的格，所以 $i$ 的真实频率 $a_i$ 一定被**完整、不打折扣**地计入 $C[j,h_j(i)]$；而碰撞只会**额外**把别的 item 的非负频率**叠加上去**。即便哈希退化到「所有 item 映到同一格」，也只是让 $\mathrm{noise}_j(i)$ 变大，下界 $a_i$ 依然成立。此处完全没用到「两两独立 / 均匀 / 随机」任何性质。

---

## 2. 取 min 的保号性

由第 1 步，集合 $\{\,C[j,h_j(i)] : j=1,\ldots,d\,\}$ 中**每一个**数都满足 $C[j,h_j(i)] \ge a_i$。

令 $m=\min_{j} C[j,h_j(i)]$，设取到最小值的指标为 $j^\star$（即 $m=C[j^\star,h_{j^\star}(i)]$）。因 $j^\star\in\{1,\ldots,d\}$，对它套用第 1 步的不等式即得 $C[j^\star,h_{j^\star}(i)] \ge a_i$，于是

$$
\hat a_i \;=\; \min_{j} C[j,h_j(i)] \;=\; C[j^\star,h_{j^\star}(i)] \;\ge\; a_i.
$$

> 一句话：**有限个每个都 $\ge a_i$ 的数，其最小值也 $\ge a_i$**。

更进一步可把误差**显式**写出：

$$
\hat a_i - a_i \;=\; \min_{j}\bigl(a_i+\mathrm{noise}_j(i)\bigr) - a_i \;=\; \min_{j}\mathrm{noise}_j(i) \;\ge\; 0.
$$

即**估计误差恰好等于 $d$ 行碰撞噪声中的最小者**，而每个 $\mathrm{noise}_j(i)$ 都是非负项之和，故误差天然 $\ge 0$。这就是「只高估、不低估」的代数根源：**误差本身的结构是一串非负量的累加，不可能是负数**。取 $\min$ 的语义只是「从 $d$ 个上界里挑最紧的一个」以**压低**正噪声；但 $a_i$ 是 $d$ 个上界共有的、不可减去的基线，故永远压不破 $a_i$ 这条地板。

至此，对**任意数据、任意哈希函数**，确定性地证得 $\hat a_i \ge a_i$——零概率假设、零期望论证。

---

## 3. 单调性推论（只增流下 $\hat a_i$ 单调不减）

设处理完前 $t$ 条更新后，真实频率为 $a_{t,i}$，计数器为 $C_t[j,\cdot]$，估计为 $\hat a_{t,i}$。证明 $\hat a_{t,i}$ 随 $t$ **单调不减**。

**(a) 每个计数器是 $t$ 的单调不减函数。**
处理第 $t{+}1$ 条更新 $(i_{t+1},c_{t+1})$ 时，每一行只往某个格加 $c_{t+1}\ge 0$，**从不减**。故对任意行 $j$、任意格 $\ell$，$C_{t+1}[j,\ell]\ge C_t[j,\ell]$；特别地 $C_{t+1}[j,h_j(i)]\ge C_t[j,h_j(i)]$。即每个 $C_t[j,h_j(i)]$ 都单调不减。

**(b) 单调不减函数族的最小值仍单调不减。**
任取 $t_1\le t_2$。由 (a)，$\forall j$ 有 $C_{t_2}[j,h_j(i)]\ge C_{t_1}[j,h_j(i)]$。设 $\hat a_{t_2,i}=C_{t_2}[j^\star,h_{j^\star}(i)]$ 取到第 $t_2$ 时刻的最小值，则

$$
\hat a_{t_2,i} \;=\; C_{t_2}[j^\star,h_{j^\star}(i)]
\;\ge\; C_{t_1}[j^\star,h_{j^\star}(i)]
\;\ge\; \min_{j} C_{t_1}[j,h_j(i)]
\;=\; \hat a_{t_1,i}.
$$

故 $\hat a_{t,i}$ 单调不减：**随着流的推进，点查询估计只会上升（或持平），绝不会下降。**

**这一条如何体现「单边误差」**：因更新恒非负，每个计数器只能被「加料」、无法被「抹除」。具体地——
- $i$ 自身的真实频率 $a_{t,i}$ 会随 $i$ 的每次出现**精确、逐条**地累加进每一行的 $C[j,h_j(i)]$（$i$ 永远命中自己那格）；
- 碰撞带来的别的 item 的非负频率也只能往里**叠加**，没有任何机制能把它抵消。

于是两端同时成立：下侧 $\hat a_{t,i}\ge a_{t,i}$ 恒真（第 1、2 步，真值是不可撤销的下确界）；上侧噪声只能**积累**。合起来：**Count-Min 只会把碰撞噪声累加进去，永远有能力抬高估计，却没有任何机制（没有负更新）能凭空抹掉 $a_i$ 或抵消已计入的噪声**。无碰撞的理想情形 $\hat a_i=a_i$（误差为 $0$）；一旦发生碰撞，误差为正，且只会随流增大。这正是论文所说的 *"The error bound here is one-sided … Because only positive quantities are added to the counters then it is possible to take the minimum instead of the median."*

---

## 结论

仅由 CM 的**更新结构（每行加非负计数）**与**查询结构（取 $d$ 行最小值）**，不借助任何概率误差界，可确定性地推出：

1. **单行**：$C[j,h_j(i)] = a_i + \mathrm{noise}_j(i)$，其中 $\mathrm{noise}_j(i)\ge 0$，故对每一行 $C[j,h_j(i)]\ge a_i$；
2. **取 min 保号**：每行都 $\ge a_i$，取 $\min$ 后 $\hat a_i\ge a_i$ 仍成立，且误差恰为 $\min_j\mathrm{noise}_j(i)\ge 0$；
3. **单调性**：在只增（$c\ge 0$）流上每个计数器单调不减，故 $\hat a_{t,i}$ 单调不减。

因此，**Count-Min 的点查询在只增模型（cash-register）下是一个单边误差估计量：它只可能高估、绝不可能低估真实频率 $a_i$**。单边性的根源是两条结构性事实——「真值 $a_i$ 被无条件保留（$i$ 永远命中自己的格）」+「误差是非负碰撞项的累加」；而「取最小值」只是从一组上界里挑最紧者，永远压不破 $a_i$ 这条地板线。

---

### 附注：非负性是关键前提（论文用「换中位数」印证了这一点）

「不低估」依赖频率非负。本题的 cash-register 模型（$c_t\ge 0$）自动保证 $a_{i'}\ge 0$，故 $\mathrm{noise}_j(i)\ge 0$ 成立。可作两点精确说明：

- 在**严格 turnstile**（允许个别 $c_t$ 为负，但净频率恒 $a_{i'}\ge 0$）模型下，第 1 步的分解 $C[j,h_j(i)]=\sum_{i':\text{碰撞}}a_{i'}=a_i+\mathrm{noise}_j(i)$ 仍成立且 $\mathrm{noise}_j(i)\ge 0$，故「不低估」结论**依然成立**。但 (a) 中「计数器单调不减」会失效，故**第 3 步的单调性推论不再成立**。
- 在**一般 turnstile**（净频率 $a_{i'}$ 可为负）模型下，$\mathrm{noise}_j(i)$ 可为负，$\hat a_i\ge a_i$ 可被破坏。论文对此情形正是改用 **$\hat a_i=\mathrm{median}_j C[j,h_j(i)]$（Theorem 2），误差变为两侧** $a_i-3\varepsilon\|a\|_1 \le \hat a_i \le a_i+3\varepsilon\|a\|_1$——这从反面印证了：**单边误差性质完全来自「只加非负量」这一结构前提**。
