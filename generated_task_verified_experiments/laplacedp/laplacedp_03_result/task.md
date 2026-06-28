[Agents]

读给定材料，做实验，写结论。

考察 ε 对实用性的影响（隐私-效用权衡）。固定一个计数/均值查询（Δf 固定），对 ε ∈ {0.01, 0.1, 0.5, 1, 2, 5} 分别：用 Laplace 机制（scale=Δf/ε）对查询输出加噪，重复多次，记录输出相对真值的平均绝对误差（MAE）与均方根误差（RMSE）。把「MAE/RMSE 随 ε 的变化」并与理论噪声尺度 Δf/ε 对比，写到 ./summary_utility_vs_epsilon.md。固定设置：查询、Δf、试验次数、随机种子；唯一自变量为 ε。

---

[Judge]

Look at `./summary_utility_vs_epsilon.md`, check whether conclusion cover the following points

1. 误差随 ε 增大（隐私减弱）而下降。
2. 误差量级符合 ~Δf/ε（Laplace 标度）。
3. 体现隐私-效用权衡。


[Judge V2]

查阅 `./summary_utility_vs_epsilon.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；Laplace 机制、MAE/RMSE vs ε）：

1. 须给误差随 ε 增大而下降（golden：MAE≈Δf/ε、ε=0.01/0.1/1/5→100/10/1/0.2；可接受：单调降）。（细化原 [Judge] 第 1 点）
2. 须给量级符合 Δf/ε（Laplace 标度）（golden：MAE=Δf/ε、RMSE=(Δf/ε)·√2、RMSE/MAE=√2、相对误差<0.4%；可接受：MAE≈Δf/ε 在常数倍内）。（细化原 [Judge] 第 2 点）
3. 须体现隐私-效用权衡（golden：ε 翻倍误差减半；可接受：点明 1/ε 权衡）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
