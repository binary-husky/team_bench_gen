[Agents]

读给定材料，做实验，写结论。

实证验证 ε-不可区分性。取计数查询 f（统计某属性的个数，全局敏感度 Δf=1），构造一对相邻数据集 D, D'（相差一行，故 f(D)−f(D')=1）。对 ε ∈ {0.1, 0.5, 1.0, 2.0} 分别：用 NumPy 从零实现 Laplace 机制 M(D)=f(D)+Lap(Δf/ε)（np.random.laplace(scale=1/ε)），对 D 与 D' 各重复约 1×10^5 次；把输出分箱成直方图，逐箱计算经验概率比 Pr[M(D)=t]/Pr[M(D')=t]，取其最大值，并与理论上界 e^ε 比较。把「经验最大概率比 vs e^ε（各 ε）」写到 ./summary_indistinguishability.md。固定设置：查询、相邻对、试验次数、分箱、随机种子；唯一自变量为 ε。

---

[Judge]

Look at `./summary_indistinguishability.md`, check whether conclusion cover the following points

1. 相邻数据集的输出经验概率比 ≤ e^ε（满足 ε-DP）。
2. 界在最坏输出处接近紧（经验比 ≈ e^ε）。
3. 整体实证确认 ε-DP 成立。


[Judge V2]

查阅 `./summary_indistinguishability.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；Laplace 机制、相邻数据集、自变量 ε）：

1. 须给相邻数据集输出经验概率比 ≤ e^ε（golden：稳健右尾比 B/e^ε=1.0063/1.0067/1.0082/0.9979（±0.8%）；可接受：总体比 ≤e^ε 且 ≈e^ε）。（细化原 [Judge] 第 1 点）
2. 须给界在最坏输出处接近紧（golden：逐箱最大 (A) 小 ε 上超 e^ε（1.59 vs 1.105）但为有限样本顺序统计伪迹、随支持增大收敛（阈值 300→1.26→e^ε=1.105）；可接受：说明逐箱最大超界为统计伪迹、总体紧）。（细化原 [Judge] 第 2 点——补有限样本伪迹说明）
3. 须整体实证 ε-DP 成立（golden：总体饱和 e^ε、ε 越小越不可区分；可接受：点明总体 ε-DP 成立）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
