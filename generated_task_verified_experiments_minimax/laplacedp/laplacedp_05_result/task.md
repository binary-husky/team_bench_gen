[Agents]

读给定材料，做实验，写结论。

考察查询敏感度 Δf 对噪声/效用的影响。固定 ε，对一组不同敏感度的查询分别加噪：(a) 计数查询（Δf=1）；(b) 区间 [0,B] 上的求和查询（Δf=B，如 B=10）；(c) n 个数据上的均值查询（Δf=1/n）。用 Laplace 机制（scale=Δf/ε），重复多次，记录各自的平均绝对误差。把「误差随查询敏感度 Δf 的变化」写到 ./summary_sensitivity.md。固定设置：ε、数据规模、试验次数、随机种子；自变量为查询类型（即 Δf）。

---

[Judge]

Look at `./summary_sensitivity.md`, check whether conclusion cover the following points

1. 敏感度越大的查询，所需噪声越大、误差越大。
2. 误差量级随 Δf 线性增长（~Δf/ε）。
3. 高敏感度查询在同等 ε 下效用更差。


[Judge V2]

查阅 `./summary_sensitivity.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；固定 ε、改变查询 Δf、测 MAE）：

1. 须给敏感度越大噪声/误差越大（golden：count Δf=1 MAE≈1、sum Δf=10 MAE≈10、mean Δf=1/N=0.001 MAE≈0.001；可接受：MAE 随 Δf 单调增）。（细化原 [Judge] 第 1 点）
2. 须给误差随 Δf 线性增长（golden：拟合斜率 1.0006、R²≈1、MAE_count/MAE_mean=1003.4≈Δf 比 1000；可接受：线性、过原点）。（细化原 [Judge] 第 2 点）
3. 须给高敏感度同等 ε 下效用更差（golden：sum 比 count 差 10×；可接受：点明高敏感度效用差）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
