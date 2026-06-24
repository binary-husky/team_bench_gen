[Agents]

读给定材料，做分析，写结论。

考虑五个连续型 ZDT 测试问题（ZDT1、ZDT2、ZDT3、ZDT4、ZDT6），它们都共享 f2 = g(x₂..xₙ)·h(f₁, g) 的结构形式，其中 f₁ 仅依赖 x₁。

请回答下面这一个问题（只需回答这一个）：

证明：在这五个问题上，决策空间中的 Pareto 最优解必然满足 x₂ = x₃ = … = xₙ = 0（即 Pareto 最优集形如 {(x₁, 0, …, 0) : x₁ ∈ [0, 1]}）。要求：
- 指出该结论依赖了 (f₁, g, h) 三者的哪几条结构性质；
- 对每条性质给出"违反它结论就不成立"的反例方向（不需要构造具体反例，只需说明哪一项假设被破坏）；
- 解释为什么同样的证明对 ZDT5 不成立——ZDT5 上 Pareto 最优解在 x₂..xₙ 维度上落到哪里、为什么。

不需要做实验或数值仿真，纯结构 + 微积分推导即可。

把分析过程和最终结论写到 `./summary_zdt_01.md`。

---

[Judge]

Look at `./summary_zdt_01.md`, check whether conclusion covers the following point (only 1 point, must be fully addressed)

1. 结论必须同时包含以下三件事才能判通过：(a) 明确指出证明依赖"g 在 x₂..xₙ 上以 x_i=0 为唯一全局最小点"和"f₂ 对 g 单调（在 Pareto 区域 ∂f₂/∂g > 0）"这两条性质（或等价的代数/微分论证）；(b) 说明若 g 不是单调或 h 不再保证 f₂ 对 g 单调，结论失效；(c) 正确指出 ZDT5 的 g 函数最小值不在 u(v_i)=0 处，而是 u(v_i)=n 处（且 g 是 deceptive 的），因此 ZDT5 的 Pareto 最优解要求每个 5-bit 子串全 1，而非全 0。
