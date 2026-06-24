[Agents]

读给定材料，仅通过逻辑推理回答下面这一个问题（不要做实验），把你的答案与推导写到 ./summary_logic.md。

问题：SimHash 用 b 个独立随机超平面的符号来表示一个向量；两个草图之间「符号一致的位数占比」估计 p = 1 − θ/π（θ 为两向量夹角）。请推导该估计的标准差随 b 如何变化，并定量回答：要把估计误差减半，需要把位数 b 增加到几倍？请在推导中指明「一致位数」所服从的分布并据此推导。

---

[Judge]

Look at `./summary_logic.md`, check whether conclusion cover the following points

1. 标准答案：b 个符号位是独立的 Bernoulli(p) 试验（p = 1 − θ/π），一致位数 K ~ Binomial(b, p)，一致占比 K/b 即估计 p̂；Var(p̂) = p(1−p)/b，故 std(p̂) = √(p(1−p)/b) = O(1/√b)；又 θ̂ = π(1 − p̂)，故 std(θ̂) = π·std(p̂) = O(1/√b)。要使标准差减半，须把 b 增大 4 倍（因 std ∝ 1/√b）。即估计误差随 O(1/√b) 下降、每次减半代价为 4 倍位数。
