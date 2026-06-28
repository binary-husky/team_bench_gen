# SimHash 估计标准差随位数 b 的变化

> 任务：仅逻辑推理——b 个独立超平面符号位，一致占比估计 p=1−θ/π；推导 std 随 b 的变化；误差减半需 b 几倍。
> 依据 Charikar, *Similarity Estimation Techniques from Rounding Algorithms* (STOC 2002)。

## 分布

b 个符号位是**独立** Bernoulli(p) 试验，`p = 1 − θ/π`（两向量夹角 θ，单个超平面分到同侧的概率）。一致位数 `K ~ Binomial(b, p)`，一致占比 `p̂ = K/b` 是 p 的估计。

## 标准差

- `Var(p̂) = p(1−p)/b` ⟹ `std(p̂) = √(p(1−p)/b) = O(1/√b)`。
- `θ̂ = π(1 − p̂)` ⟹ `std(θ̂) = π·std(p̂) = O(1/√b)`。

## 误差减半需 b 增几倍

`std ∝ 1/√b`。要 std 减半：`1/√b' = (1/2)(1/√b)` ⟹ `√b' = 2√b` ⟹ **`b' = 4b`**。

## 一句话总结

一致位数 `K~Binomial(b,p)`、`p=1−θ/π`；`std(p̂)=√(p(1−p)/b)=O(1/√b)`，`std(θ̂)=π·std(p̂)=O(1/√b)`；误差减半需 b 增 4 倍（std∝1/√b）。
