# SimHash 估计 p = 1 − θ/π 的标准差推导

## 题目（原文）

> SimHash 用 b 个独立随机超平面的符号来表示一个向量；两个草图之间「符号一致的位数占比」估计 p = 1 − θ/π（θ 为两向量夹角）。请推导该估计的标准差随 b 如何变化，并定量回答：要把估计误差减半，需要把位数 b 增加到几倍？请在推导中指明「一致位数」所服从的分布并据此推导。

本文根据所给材料 Charikar (STOC'02, Section 3) 严格推导。

---

## 1. 模型设定

给定两个 d 维非零向量 **u**, **v**，其夹角为 θ ∈ [0, π]。

**SimHash 定义**（Charikar 2002, §3）：
1. 独立采样 b 个 d 维标准正态向量 **r**₁, **r**₂, …, **r**_b（即每个分量独立同分布于 N(0,1)）。
2. 第 i 个超平面由 **r**_i 决定，其符号哈希为
   $$h_{\mathbf r_i}(\mathbf x) = \mathbb{1}\{\mathbf r_i \cdot \mathbf x \ge 0\}\in\{0,1\}$$
3. 两个向量各得到 b 位草图 $h(\mathbf u), h(\mathbf v) \in \{0,1\}^b$。

**碰撞概率（关键引理，Charikar 2002, §3）**：
$$\Pr\!\left[h_{\mathbf r_i}(\mathbf u) = h_{\mathbf r_i}(\mathbf v)\right] = 1 - \frac{\theta(\mathbf u,\mathbf v)}{\pi} \triangleq p.$$

直观上，随机高斯向量 **r** 的方向在球面上均匀；**r** 与 **u**, **v** 同时保持同号（即 **r** 落在由 **u**, **v** 张成的角域之外）的概率恰为 (π − θ)/π = 1 − θ/π。

---

## 2. 「一致位数」的分布

定义第 i 位一致指示变量
$$X_i = \mathbb{1}\{h_{\mathbf r_i}(\mathbf u) = h_{\mathbf r_i}(\mathbf v)\}.$$

由于 **r**₁, …, **r**_b 相互独立，且每个 X_i 服从以 p = 1 − θ/π 为成功概率的伯努利分布（Bernoulli(p)），故「一致位数」

$$\boxed{X = \sum_{i=1}^{b} X_i \;\sim\; \mathrm{Binomial}(b,\,p)}$$

严格服从二项分布 B(b, p)（精确有限样本分布，并非渐近）。

其矩为
- $\mathbb E[X] = bp$，
- $\mathrm{Var}(X) = bp(1-p)$，
- $\mathrm{SD}(X) = \sqrt{bp(1-p)}$。

---

## 3. 「一致位数占比」的估计量及其标准差

定义估计量
$$\hat p = \frac{X}{b} = \frac{1}{b}\sum_{i=1}^{b} X_i.$$

- **无偏性**：$\mathbb E[\hat p] = \mathbb E[X]/b = p$。
- **方差**（因 X_i 独立同分布，且 Var(X_i)=p(1−p)）：
$$\mathrm{Var}(\hat p) = \frac{\mathrm{Var}(X)}{b^2} = \frac{bp(1-p)}{b^2} = \frac{p(1-p)}{b}.$$
- **标准差**：
$$\boxed{\;\mathrm{SD}(\hat p) = \sqrt{\frac{p(1-p)}{b}} = \frac{\sqrt{p(1-p)}}{\sqrt{b}}\;}$$

**标度律**：
$$\mathrm{SD}(\hat p) \;\propto\; \frac{1}{\sqrt{b}}.$$

即位数 b 每扩大 k 倍，标准差缩小 $\sqrt k$ 倍（典型的参数估计 1/√n 速率）。

---

## 4. 渐近正态性（大 b 时的近似）

由中心极限定理：
$$\hat p \;\xrightarrow{d}\; \mathcal N\!\left(p,\; \frac{p(1-p)}{b}\right).$$

因此 b 位 SimHash 给出的 95% 置信区间近似为
$$\hat p \pm 1.96\sqrt{\frac{p(1-p)}{b}}.$$

需要更小置信区间宽度 ε（如 ε = 0.05）的最小位数为
$$b \;\ge\; \left(\frac{z_{\alpha/2}}{\varepsilon}\right)^2 p(1-p).$$

---

## 5. 定量回答：要把估计误差减半，b 需扩大到几倍？

设当前位数 $b_0$，标准差
$$\sigma_0 = \sqrt{p(1-p)/b_0}.$$

要求新位数 $b_1$ 使 $\sigma_1 = \tfrac{1}{2}\sigma_0$：
$$\sqrt{\frac{p(1-p)}{b_1}} = \frac{1}{2}\sqrt{\frac{p(1-p)}{b_0}}.$$

两边平方并消去 $p(1-p)>0$（除非 θ=0 或 θ=π 的退化情形）：
$$\frac{1}{b_1} = \frac{1}{4}\cdot\frac{1}{b_0} \;\Longrightarrow\; b_1 = 4\,b_0.$$

**结论**：要把 SimHash 对 $p=1-\theta/\pi$ 的估计误差（标准差）减半，需将位数 b **扩大到原来的 4 倍**。

---

## 6. 与一般情形的对照

上述结论与任何「用 n 次独立 Bernoulli 抽样估计成功概率 p」的标准差公式
$$\mathrm{SD} = \sqrt{p(1-p)/n}$$
完全一致。SimHash 的特殊性仅在于：
- 每次抽样的成功概率 $p = 1 - \theta/\pi$ 与向量夹角直接挂钩；
- 估计对象是角度/相似度而非任意伯努利参数。

推导依据仅为：(i) Charikar §3 给出的碰撞概率 $p=1-\theta/\pi$；(ii) b 次独立抽样的二项分布方差公式。

---

## 7. 一句话总结

| 量 | 表达式 |
|---|---|
| 一致位数 X 的分布 | $\mathrm{Binomial}(b,\,1-\theta/\pi)$ |
| 估计量 | $\hat p = X/b$ |
| 标准差 | $\mathrm{SD}(\hat p) = \sqrt{p(1-p)/b} \propto 1/\sqrt{b}$ |
| 误差减半所需 b 倍数 | **b → 4 b**（扩大 4 倍） |