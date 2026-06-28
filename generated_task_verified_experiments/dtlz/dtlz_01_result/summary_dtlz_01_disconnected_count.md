# DTLZ7 不连通 Pareto 前沿段数 2^(M-1) 的推导

> 任务：纯粹从论文式 (6.25) 的构造出发，**不进行任何代码实验**，仅用逻辑推理与微积分推导，复现论文 §6.7.7 中未给推导的结论 "This test problem has 2^(M-1) disconnected Pareto-optimal regions"。

## 0. 原始构造（式 6.25）

DTLZ7（Deb–Thiele–Hans–Zitzler, §6.7.7 / 式 6.25）：

$$
\begin{aligned}
&\min\; f_1(x_1)=x_1,\;\; f_2(x_2)=x_2,\;\dots,\; f_{M-1}(x_{M-1})=x_{M-1},\\
&\min\; f_M(x)=(1+g(x_M))\,h(f_1,\dots,f_{M-1},g),\\[2pt]
&g(x_M)=1+\sum_{x_i\in x_M} x_i^2,\qquad |x_M|=k=n-M+1,\\
&h(f_1,\dots,f_{M-1},g)=M-\sum_{i=1}^{M-1}\frac{f_i}{1+g}\bigl(1+\sin(3\pi f_i)\bigr),\\
&0\le x_i\le 1.
\end{aligned}
$$

论文给出：Pareto 最优解对应 $x_M=0$（即 $g=0$），且"有 $2^{M-1}$ 段不连通区域"，但未给推导。下面自行推出。

---

## 1. 全局 Pareto 前沿上的 $f_M(f_1,\dots,f_{M-1})$ 显式表达式

在全局 Pareto 前沿上 $x_M=0$，故

$$
g(x_M)=0 \;\Longrightarrow\; 1+g=1.
$$

又 $f_i=x_i$（$i=1,\dots,M-1$），各自独立取值于 $[0,1]$，互不耦合。把 $1+g=1$ 代入 $h$ 再代入 $f_M=(1+g)h$：

$$
\boxed{\;f_M(f_1,\dots,f_{M-1})=M-\sum_{i=1}^{M-1} f_i\bigl(1+\sin(3\pi f_i)\bigr)\;}
$$

（若采用某些文献把 $h$ 首项写成 $M-1$ 的版本，只是把常数 $M$ 换成 $M-1$；这一常数偏移对下面的导数与段数计数毫无影响。）

记 $\psi(t)\triangleq t\bigl(1+\sin(3\pi t)\bigr)$，则前沿曲面可写成

$$
f_M = M-\sum_{i=1}^{M-1}\psi(f_i).
$$

关键结构：$f_M$ 是**各项可加、且每项只依赖各自的 $f_i$** 的函数。正是这一可加性使后面"逐维独立"成立。

---

## 2. Pareto 最优性条件（逐维独立）

问题对每个 $f$ 都是 $\min$。固定除 $f_i$、$f_M$ 外的所有 $f_j$（$j\neq i,M$），在 $(f_i,f_M)$ 平面内得到一个 2-目标子问题，其前沿就是曲面 $f_M=M-\psi(f_i)-\text{const}$ 在该切片上的曲线。

点 Pareto 最优 $\iff$ 不能把 $(f_i,f_M)$ 同时减小。沿曲线移动：$df_M=\dfrac{\partial f_M}{\partial f_i}\,df_i$。若要让 $f_i$ 减小（$df_i<0$）的同时 $f_M$ 也减小（$df_M<0$），就需要 $\dfrac{\partial f_M}{\partial f_i}>0$。因此

$$
\boxed{\;\text{Pareto 最优}\iff \frac{\partial f_M}{\partial f_i}\le 0\quad\text{对每个 }i\in\{1,\dots,M-1\}\text{ 同时成立}\;}
$$

（等价地，由于 $f_M=M-\psi(f_i)-\text{const}$，$\partial f_M/\partial f_i=-\psi'(f_i)$，上式即 $\psi'(f_i)\ge 0$：在 Pareto 前沿上 $\psi$ 沿 $f_i$ 方向非降——减小 $f_i$ 不会换来 $f_M$ 的下降，所以无法被支配。）

**为何逐维独立**：由步骤 1，$f_M$ 对 $f_i$ 求偏导时，其余 $f_j$（$j\neq i$）的项视为常数而消失，偏导只含 $f_i$：

$$
\frac{\partial f_M}{\partial f_i}=-\psi'(f_i),\qquad\text{与 }f_j\;(j\neq i)\text{ 无关。}
$$

于是 $M-1$ 个条件各自只约束自己的 $f_i$，彼此不耦合。Pareto-可行集就是各维可行区间 $\{f_i:\psi'(f_i)\ge 0\}$ 的笛卡尔积。

---

## 3. 计算 $\partial f_M/\partial f_i$，求 $f_i$ 的 Pareto-可行子集（2 段不连通）

$$
\frac{\partial f_M}{\partial f_i}
=-\frac{d}{df_i}\Bigl[f_i\bigl(1+\sin(3\pi f_i)\bigr)\Bigr]
=-\Bigl[\bigl(1+\sin(3\pi f_i)\bigr)+3\pi f_i\cos(3\pi f_i)\Bigr].
$$

记 $t\equiv f_i\in[0,1]$，定义

$$
\varphi(t)\triangleq 1+\sin(3\pi t)+3\pi t\cos(3\pi t)\quad(=\psi'(t)).
$$

由步骤 2，Pareto-可行 $\iff \varphi(t)\ge 0$。下面定出 $\varphi$ 在 $[0,1]$ 上的根与符号。

利用 $3\pi t$ 在 $[0,3\pi]$ 上走完一个半周期，逐点查 $\varphi$：

| $t$ | $3\pi t$（度） | $\sin$ | $\cos$ | $\varphi(t)=1+\sin+3\pi t\cos$ | 符号 |
|---|---|---|---|---|---|
| 0    | 0°   | 0      | 1       | $1+0+0=1$            | $+$ |
| 0.05 | 27°  | 0.454  | 0.891   | $1.454+0.420=1.874$  | $+$ |
| 0.25 | 135° | 0.707  | −0.707  | $1.707-1.667=+0.040$ | $+$ |
| 0.2515 | ~135.8° | ~0.700 | ~−0.714 | $\approx 0$ | $0$（根 $t_1$）|
| 0.30 | 162° | 0.309  | −0.951  | $1.309-2.689=-0.380$| $-$ |
| 0.40 | 216° | −0.588 | −0.809  | $0.412-3.050=-2.638$| $-$ |
| 0.50 | 270° | −1     | 0       | $1-1+0=0$           | $0$（根 $t_2$）|
| 0.55 | 297° | −0.891 | 0.454   | $0.109+2.353=+2.462$| $+$ |
| 0.70 | 378°(=18°) | 0.309 | 0.951 | $1.309+6.275=+7.584$| $+$ |
| 0.85 | 459°(=99°) | 0.988 | −0.156 | $1.988-1.253=+0.735$| $+$ |
| 0.859 | ~464°(=104°) | ~0.969 | ~−0.249 | $\approx 0$ | $0$（根 $t_3$）|
| 0.90 | 486°(=126°) | 0.809 | −0.588 | $1.809-4.986=-3.177$| $-$ |
| 1.00 | 540°(=180°) | 0 | −1 | $1-3\pi=-8.425$| $-$ |

符号序列：$+\;(\to 0\text{ 于 }t_1)\;\to -\;(\to 0\text{ 于 }t_2)\;\to +\;(\to 0\text{ 于 }t_3)\;\to -$。

为确认每个区间内不再有额外根，看 $\varphi'(t)=6\pi\cos(3\pi t)-9\pi^2 t\sin(3\pi t)$：

- 在 $(t_1,t_2)\approx(0.2515,0.5)$：$3\pi t\in(0.75\pi,1.5\pi)$，$\cos<0$、$\sin$ 先正后负但 $t$ 已使第二项主导，$\varphi$ 单调减且始终 $<0$，仅在 $t_2$ 回到 $0$——单根。
- 在 $(t_3,1]\approx(0.859,1]$：$3\pi t\in(2\pi+1.78,\,2\pi+\pi)$，$\cos<0$、$\sin>0$，故 $\varphi'=6\pi(\text{负})-9\pi^2 t(\text{正})<0$，$\varphi$ 严格递减，无回头根。

因此 $\varphi(t)\ge 0$ 的解集恰为两段不连通闭区间：

$$
\boxed{\;\{t\in[0,1]:\varphi(t)\ge 0\}=[0,\,t_1]\cup[t_2,\,t_3]\;}
$$

数值上

$$
t_1\approx 0.2515\;(\text{约 }0.25),\qquad t_2=0.50,\qquad t_3\approx 0.859\;(\text{约 }0.86).
$$

（题目所给 $t_1\approx0.30,\,t_2=0.50,\,t_3\approx0.85$ 为粗略示意；精确解为 $t_1\approx0.2515$、$t_3\approx0.859$，$t_2=0.5$ 精确命中，因为 $\sin(3\pi/2)=-1$、$\cos(3\pi/2)=0$ 使 $\varphi(0.5)=1-1+0=0$。三者定性一致：每维 2 段。）

可作一致性校验：$\psi(t)=t(1+\sin(3\pi t))$ 在 $t_1$ 取局部极大（$\psi(0.2515)\approx0.428$），在 $t_2=0.5$ 取局部极小（$\psi(0.5)=0$），在 $t_3$ 取局部极大（$\psi(0.859)\approx1.70$）；可行区间正是 $\psi$ 非降的部分 $[0,t_1]\cup[t_2,t_3]$，与"Pareto $\iff\psi'\ge0$"完全吻合。

---

## 4. 综合：$2^{M-1}$ 计数

由步骤 2，$M-1$ 个 Pareto 条件**逐维独立**，每维 $f_i$ 的可行集都是步骤 3 给出的 **2 段不连通区间** $[0,t_1]\cup[t_2,t_3]$。整个 Pareto 前沿是这 $M-1$ 个 2-段集合的笛卡尔积：

$$
\text{不连通段数}= \underbrace{2\times 2\times\cdots\times 2}_{M-1\text{ 个维度}}
=\boxed{\,2^{M-1}\,}.
$$

校验：$M=3$ 时 $2^{3-1}=4$ 段，与论文图 6.24/6.25 中"both algorithms ... in all **four** disconnected Pareto-optimal regions"一致。

---

## 一句话总结

**DTLZ7 的不连通段数 $2^{M-1}$ 是 $h$ 函数中 $\sin(3\pi f_i)$ 项造成的——$\sin$ 项使每个 $f_i$ 维度上有 2 个 Pareto-可行子区间，$M-1$ 个维度的笛卡尔积给出总段数。**
