[Agents]

读给定材料，做实验，写结论。

考察组合查询下隐私损失的累积。固定总隐私预算 ε_total，对查询数 k ∈ {1, 5, 10, 20, 50}：把预算均分，每次查询的 ε_q = ε_total/k（基本组合定理下总损失为 k·ε_q = ε_total）。对每个 k，用 Laplace 机制（scale=Δf/ε_q）对每次查询加噪，记录单次查询的平均误差（应 ~Δf/ε_q = k·Δf/ε_total）。把「单次查询误差随 k 的变化」写到 ./summary_composition.md。固定设置：查询、Δf、ε_total、试验次数、随机种子；唯一自变量为 k。

---

[Judge]

Look at `./summary_composition.md`, check whether conclusion cover the following points

1. 为保持总 ε_total 不变，单次 ε_q 随 k 增大而按 1/k 缩小。
2. 单次查询噪声/误差随 k 线性增长（~k·Δf/ε_total）。
3. 体现隐私预算随查询数线性消耗（基本组合）。


[Judge V2]

查阅 `./summary_composition.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；k 次组合查询、ε_total 固定、ε_q=ε_total/k）：

1. 须给单次 ε_q 随 k 按 1/k 缩小（golden：ε_q=ε_total/k；可接受：点明 1/k）。（细化原 [Judge] 第 1 点）
2. 须给单次误差随 k 线性增长（golden：k=1→~1.0、k=50→~50.3（放大 50×）、实测/理论~1；可接受：线性增长、≈k·Δf/ε_total）。（细化原 [Judge] 第 2 点）
3. 须体现隐私预算随查询数线性消耗（基本组合）（可接受：点明基本组合定理）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
