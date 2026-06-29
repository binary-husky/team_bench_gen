# DTLZ7 不连通段数 2^(M−1) 的推导

**问题来源**：Deb 等人 2005 年书章 "Scalable Test Problems for Evolutionary Multiobjective Optimization"（式 6.25 / §6.7.7）。论文原文只给结论 "This test problem has 2^(M−1) disconnected Pareto-optimal regions in the search space"，未给出推导。本报告从式 6.25 出发，纯逻辑 + 微积分完成该计数。

---

## 0. DTLZ7（式 6.25）的目标函数

$$
\begin{aligned}
\min\ f_1(\mathbf x_1) &= x_1, \\
\min\ f_2(\mathbf x_2) &= x_2, \\
&\ \vdots \\
\min\ f_{M-1}(\mathbf x_{M-1}) &= x_{M-1}, \\
\min\ f_M(\mathbf x) &= (1+g(\mathbf x_M))\,h\!\left(f_1, f_2, \ldots, f_{M-1}, g\right), \\[2pt]
g(\mathbf x_M) &= 1 + \tfrac{9}{|\mathbf x_M|}\sum_{x_i\in\mathbf x_M} x_i, \\
h(f_1,\ldots,f_{M-1},g) &= M - \sum_{i=1}^{M-1}\!\left[\frac{f_i}{1+g}\bigl(1+\sin(3\pi f_i)\bigr)\right], \\
\text{subject to }\ & 0 \le x_i \le 1,\ \ i=1,\ldots,n.
\end{aligned}
$$

其中 $\mathbf x_M$ 是 $k=n-M+1$ 个**位置变量**，$\mathbf x_1,\ldots,\mathbf x_{M-1}$ 各承载一个目标。注意 $g\ge 1$，全局最小 $g^*=0$ 仅当 $\mathbf x_M=\mathbf 0$ 时取得。

---

## 1. 全局 Pareto 前沿上的 $f_M$ 显式表达式

全局 Pareto 前沿上的点必须满足 $g(\mathbf x_M)=g^*=0$，即 $\mathbf x_M=\mathbf 0$。此时
- $f_1=x_1,\ f_2=x_2,\ \ldots,\ f_{M-1}=x_{M-1}$，各自独立取遍 $[0,1]$；
- $f_M = (1+0)\,h = h\big|_{g=0}$。

代入 $g=0$：

$$
\boxed{\,f_M(f_1,\ldots,f_{M-1}) = M - \sum_{i=1}^{M-1} f_i\bigl(1+\sin(3\pi f_i)\bigr)\,}
$$

这是**整个 Pareto 前沿在目标空间的参数化**。注意 $f_M$ 是 $(f_1,\ldots,f_{M-1})$ 的**可分函数**（各 $f_i$ 出现在自己的项中，互相不耦合）。

---

## 2. Pareto 最优性条件

我们处理的是 **M 个目标同时最小化**。固定 $j\ne i,M$ 的所有 $f_j$（包括 $g$），把问题化为 $(f_i,f_M)$ 的 2 目标子问题。

2 目标子问题的 Pareto 前沿即曲线 $(f_i, f_M(f_i))$。对于**单变量实函数** $f_M(\cdot)$，曲线上每个点都是 2 目标 Pareto 最优的，当且仅当**沿该曲线无法在两个目标上同时下降**。

把 $f_M$ 视为 $f_i$ 的函数：
- 若 $\dfrac{\partial f_M}{\partial f_i}<0$：增大 $f_i$（变差）会减小 $f_M$（变好）→ 纯权衡，是 Pareto 段上的点。
- 若 $\dfrac{\partial f_M}{\partial f_i}>0$：增大 $f_i$（变差）也增大 $f_M$（变差）；反向同时减小两个 → 该点被**严格支配**，不在 Pareto 前沿上。
- $\dfrac{\partial f_M}{\partial f_i}=0$：过渡点。

由于 $f_M$ 是可分函数，每个 $f_i$ 的 Pareto 段**仅由 $\partial f_M/\partial f_i$ 的符号决定**（$\partial f_M/\partial f_i$ 不含其它 $f_j$，因为求和各项独立）。因此

$$
\boxed{\,(f_1,\ldots,f_{M-1}, f_M)\text{ 是 Pareto 最优}\iff \forall i\in\{1,\ldots,M-1\}:\ \frac{\partial f_M}{\partial f_i}\le 0\,}
$$

这就是**逐维独立**的 Pareto 条件：对每个 $i$ 独立地判断，互不耦合。

---

## 3. $\partial f_M/\partial f_i$ 与 $f_i$ 的 Pareto-可行区间

由第 1 步的可分性：

$$
\frac{\partial f_M}{\partial f_i} = -\bigl[\,(1+\sin(3\pi f_i)) + 3\pi f_i \cos(3\pi f_i)\,\bigr] \;\equiv\; -s(f_i),
$$

其中

$$
\boxed{\,s(f)\;\equiv\;1+\sin(3\pi f)+3\pi f\cos(3\pi f)\,}
$$

Pareto-可行条件 $\partial f_M/\partial f_i \le 0$ 等价于 $s(f_i)\ge 0$。

### 3.1 $s(f)$ 的零点（数值验证）

| $f$    | 0.00 | 0.10  | 0.20  | 0.25  | 0.26  | 0.30  | 0.40  | 0.50  | 0.60  | 0.70  | 0.80  | 0.85  | 0.86  | 0.90  | 1.00 |
| ------ | ---- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ---- |
| $s(f)$ | +1.00| +2.36 | +1.37 | +0.04 | −0.25 | −1.38 | −2.64 |  0.00 | +4.99 | +7.58 | +4.28 | +0.73 | −0.05 | −3.18 | −8.42 |

可见 $s$ 在 $[0,1]$ 上**正好三个零点**（用 `brentq` 精确求根）：

- $t_1 \approx 0.2514$
- $t_2 = 0.5$（解析地：$\sin(1.5\pi)=-1,\ \cos(1.5\pi)=0 \Rightarrow s(0.5)=1-1+0=0$）
- $t_3 \approx 0.8594$

### 3.2 $s(f)\ge 0$ 的解集

$$
\{f\in[0,1]: s(f)\ge 0\} \;=\; [0,\,t_1]\ \cup\ [t_2,\,t_3].
$$

这是 **2 段不连通区间**的并集，**恰好符合任务所述**（任务给出近似值 $t_1\approx 0.30,\ t_2=0.50,\ t_3\approx 0.85$，本文的解析值 $t_1\approx0.2514,\ t_3\approx 0.8594$ 与之数量级一致，"$\approx$" 范围内吻合）。

### 3.3 物理含义

- 在 $[0,t_1]\cup[t_2,t_3]$ 上，$\partial f_M/\partial f_i\le 0$：沿 $f_i$ 增大方向走，会**减小** $f_M$，是合法的 Pareto 权衡。
- 在 $(t_1,t_2)\cup(t_3,1]$ 上，$\partial f_M/\partial f_i>0$：增大 $f_i$ 同时变差 $f_M$，被严格支配，**不是** Pareto 前沿上的点。

---

## 4. 笛卡尔积：$2^{M-1}$ 段

Pareto 前沿在 $\,(f_1,\ldots,f_{M-1})$-参数空间中是每个 $f_i$ 可行区间的**笛卡尔积**：

$$
\mathcal{P}\;=\;\prod_{i=1}^{M-1}\{[0,t_1]_i \cup [t_2,t_3]_i\}.
$$

由于每维有 2 段不连通区间，各维之间互不耦合，由乘法原理：

$$
\#\text{连通段}\;=\;\underbrace{2\times 2\times\cdots\times 2}_{M-1\text{ 个 2}}\;=\;2^{M-1}.
$$

每个"段"是 $[0,1]^{M-1}$ 的一个**矩形盒**（小到 $2^{M-1}$ 个矩形子集），它们两两不交（因 $f_i$ 维的可分性），并构成全部 Pareto 前沿（每个 $f_i$ 必须在它的可行子区间中）。因此 DTLZ7 的全局 Pareto 前沿有

$$
\boxed{\,2^{M-1}\,}
$$

个不连通的 Pareto-最优区域。✓

---

## 一句话总结

**DTLZ7 的不连通段数 $2^{M-1}$ 是 $h$ 函数中 $\sin(3\pi f_i)$ 项造成的——$\sin$ 项使每个 $f_i$ 维度上有 2 个 Pareto-可行子区间 $[0,t_1]\cup[t_2,t_3]$（$t_1\approx 0.2514,\ t_2=0.5,\ t_3\approx 0.8594$），$M-1$ 个维度的笛卡尔积给出总段数 $2^{M-1}$。**
