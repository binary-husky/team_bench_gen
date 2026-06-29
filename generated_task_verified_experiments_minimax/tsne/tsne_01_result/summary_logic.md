# t-SNE 当目标困惑度 > n−1 时的行为：纯逻辑推导

> 资料：van der Maaten & Hinton, "Visualizing Data using t-SNE", JMLR 9 (2008) 2579–2605（`tsne_material/` 中）
> 任务要求**不跑实验**，仅从论文给出的公式进行推理。

---

## 1. 回顾相关定义

对每个数据点 $i$，高维条件相似度定义为以 $i$ 为中心、带宽 $\sigma_i$ 的高斯（论文 Eq. (1)）：

$$
p_{j\mid i}=\frac{\exp\!\left(-\|x_i-x_j\|^2/2\sigma_i^2\right)}{\sum_{k\neq i}\exp\!\left(-\|x_i-x_k\|^2/2\sigma_i^2\right)},\qquad p_{i\mid i}=0.
$$

这是一个定义在 **$n-1$ 个类别** $\{j\neq i\}$ 上的概率分布。  
其 Shannon 熵（论文第 2582 页脚注 3）满足

$$
H(P_i)\in\bigl[0,\;\log_2(n-1)\bigr].
$$

困惑度（perplexity）定义为

$$
\operatorname{Perp}(P_i)=2^{H(P_i)}\in[1,\;n-1].
$$

**关键引理 1（论文脚注 3）**：困惑度是 $\sigma_i$ 的单调递增函数；$\sigma_i\to 0$ 时 $\operatorname{Perp}\to 1$，$\sigma_i\to\infty$ 时 $\operatorname{Perp}\to n-1$。

二分搜索的过程就是：在 $\sigma_i$ 的某个区间上不断折半，把 $\operatorname{Perp}(P_i)$ 推向用户给定的 $\operatorname{Perp}$。

---

## 2. 目标困惑度 $\operatorname{Perp}>n-1$ 时的二分搜索极限

设用户给定的目标为 $U>n-1$。由引理 1，$\operatorname{Perp}(\sigma_i)$ 关于 $\sigma_i$ 单调且**严格**有上界 $n-1$，因此

$$
\forall\,\sigma_i\in[0,\infty):\quad \operatorname{Perp}(\sigma_i)\le n-1 < U.
$$

二分搜索判据 $\operatorname{Perp}(\sigma_i)\stackrel{?}{<}U$ 永远为真，"mid 偏大"的一支永远会被选中；搜索区间在 $+\infty$ 一侧不断被放大。

> **结论 1**：二分搜索会把 $\sigma_i$ 推向 $\boxed{\sigma_i\to\infty}$，但永远收不到目标 $U$，困惑度被**饱和**在最大值 $n-1$。

---

## 3. $p_{\,\cdot\,|\,i}$ 的极限形式

令 $\sigma_i\to\infty$，则 $\|x_i-x_j\|^2/2\sigma_i^2\to 0$，于是

$$
\exp\!\left(-\|x_i-x_j\|^2/2\sigma_i^2\right)\to 1\quad\text{对所有 }j\neq i.
$$

因此分子分母中所有指数项都相等，$p_{\cdot|i}$ 退化成 $n-1$ 个类别上的**均匀分布**：

$$
\boxed{\,p_{j\mid i}\;\longrightarrow\;\frac{1}{n-1}\quad\forall\,j\neq i.\,}
$$

**此时 $P_i$ 携带的关于 $x_i$ 与其它点相似度的信息量为 0**：条件相似度与成对距离完全无关，所有邻居被一视同仁。

> **结论 2**：每个条件分布 $P_i$ 都退化为离散均匀分布；其熵达到上界 $H(P_i)=\log_2(n-1)$，困惑度等于 $n-1$。

---

## 4. 对称化后的联合相似度 $P$

论文 3.1 节（Eq. (5) 之前一段）定义对称化：

$$
p_{ij}=\frac{p_{j\mid i}+p_{i\mid j}}{2n},\qquad p_{ii}=0.
$$

把 $p_{\cdot|i}\equiv 1/(n-1)$ 代入：

$$
p_{ij}=\frac{\dfrac{1}{n-1}+\dfrac{1}{n-1}}{2n}=\frac{1}{n(n-1)},\qquad i\neq j.
$$

因此 $P$ 矩阵的**非对角线元素全部相等**：

$$
\boxed{\,P_{ij}=\frac{1}{n(n-1)}\quad\forall\,i\neq j,\qquad P_{ii}=0.\,}
$$

> **结论 3**：联合相似度矩阵 $P$ 退化为**完全均匀**——每个点对之间的"高维相似度"被强制拉成同一个常数，与数据点的真实几何结构无关。

直观解释：在 $n$ 个点上构造一个**联合**分布，要满足 $\sum_j p_{ij}\le 1/n$（论文 3.1 节"this ensures that $\sum_j p_{ij}\ge 1/2n$"，但当 $P_i$ 均匀时取到等号），$p_{ij}=1/(n(n-1))$ 恰好把这个上界打满——所有点对都被赋予完全相同的"邻居概率"。

---

## 5. 低维嵌入 $Q$ 与最终形态

低维端用自由度为 1 的 Student-$t$（等价于 Cauchy），论文 Eq. (4)：

$$
q_{ij}=\frac{\bigl(1+\|y_i-y_j\|^2\bigr)^{-1}}{\sum_{k\neq l}\bigl(1+\|y_k-y_l\|^2\bigr)^{-1}},\qquad q_{ii}=0.
$$

代价函数（论文 Eq. (5)）：

$$
C=\operatorname{KL}(P\|Q)=\sum_{i\neq j}p_{ij}\log\frac{p_{ij}}{q_{ij}}.
$$

### 5.1 优化目标分析

由于 $P_{ij}\equiv 1/(n(n-1))$ 是常数：

$$
C=\underbrace{\sum_{i\neq j}p_{ij}\log p_{ij}}_{\text{常数}}-\sum_{i\neq j}p_{ij}\log q_{ij}.
$$

第一项与 $y$ 无关。第二项是把 $Q$ 在均匀权重下的对数期望取负号 —— 也就是"让 $Q$ 在均匀权重下**熵最大**"。最大熵分布在 $Q$ 的形式约束下就是**均匀分布**：

$$
q_{ij}\equiv \frac{1}{n(n-1)}\quad\forall\,i\neq j.
$$

### 5.2 让 $Q$ 均匀的几何条件

$q_{ij}$ 均匀要求所有 $1+\|y_i-y_j\|^2$ 相等，即

$$
\boxed{\,y_1=y_2=\cdots=y_n.\,}
$$

**全部数据点坍缩到同一个位置。**

### 5.3 梯度角度的验证

论文 Eq. (5) 的梯度：

$$
\frac{\partial C}{\partial y_i}=4\sum_j\bigl(p_{ij}-q_{ij}\bigr)(y_i-y_j)\bigl(1+\|y_i-y_j\|^2\bigr)^{-1}.
$$

把 $p_{ij}$ 视为常数 $c=1/(n(n-1))$：

- 若 $y_1=\cdots=y_n=y^*$，则 $y_i-y_j=0$，梯度恒为 0 —— **所有点重合是一个（平凡的）驻点**。
- 由于常数 $c$ 没有指向性，"吸引力"项 $\sum_j c\,(y_i-y_j)(\cdot)$ 也不再"拉扯"任何特定方向。

> **结论 4**：梯度下降中吸引力与排斥力都"不知道该把点推到哪里"，所有 $y_i$ 在数值上会被困在初始化的小球 $\mathcal{N}(0,10^{-4}I)$ 内（论文 Algorithm 1）。若使用了**早期放大**（early exaggeration，论文 3.4 节，把 $p_{ij}$ 乘以 4），这种坍缩会更彻底 —— $p_{ij}$ 进一步偏离 $q_{ij}$，但二者的均匀性都不变；早放大的目的是"鼓励 $q_{ij}$ 变得很大"，而 $q_{ij}$ 最大的方式正是让所有 $y$ 重合。

### 5.4 与"正常 t-SNE"对比

| 量 | 正常 $\operatorname{Perp}\in[5,50]$ | 错误 $\operatorname{Perp}>n-1$ |
|---|---|---|
| $\sigma_i$ | 有限、依局部密度自适应 | $\to\infty$ |
| $p_{j\mid i}$ | 局部尖锐/平坦，编码距离 | $1/(n-1)$（均匀） |
| $P_{ij}$ | 反映真实近邻结构 | 全部等于 $1/(n(n-1))$ |
| 低维 $Q$ | 反映高维近邻的 Student-$t$ 拟合 | 最优解：均匀 $Q$ |
| 嵌入 $\mathcal{Y}$ | 有意义的聚类 / 流形 | **所有点坍缩成一点** |

---

## 6. 一句话总结

当用户把困惑度误设到 $n-1$ 以上时：

1. **二分搜索极限**：$\sigma_i$ 不断放大、永远到不了目标，困惑度被卡在 $n-1$。
2. **条件分布**：$p_{j\mid i}\equiv 1/(n-1)$（高斯退化为常数），完全失去对距离的分辨力。
3. **对称联合分布**：$P_{ij}\equiv 1/(n(n-1))$，所有点对的相似度被强制为同一常数。
4. **最终嵌入**：KL 散度在 $P$ 均匀的约束下被最小化于"$Q$ 也均匀"处，对应几何上**所有 $y_i$ 坍缩到同一点**，可视化结果没有任何可解读的聚类或流形结构。

也就是说，目标困惑度大于 $n-1$ 时，t-SNE 输出了一个**与原始高维数据完全无关的平凡解**——所有点重叠在一个点上。这正是为什么论文第 2582 页把"5 到 50"作为典型取值范围，而 $n-1$ 是算法对目标困惑度隐含的硬上限。
