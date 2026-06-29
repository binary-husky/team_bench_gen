[Agents]

读给定材料，做实验，写结论。

考察 SimHash 用汉明距离估计余弦相似度的精度随位数 b 的变化。生成若干对随机向量（d=100 维，约 1000 对，固定随机种子）并已知其余弦相似度；对 b ∈ {16, 64, 256, 1024} 分别用 NumPy 从零实现 SimHash（sketch = sign(G @ v)，G 为 b×d 随机高斯矩阵），由两草图的汉明距离估计余弦角/余弦相似度，计算估计误差（MAE / RMSE）。把「估计误差 随 b 的变化」并与 O(1/√b) 对比，写到 ./summary_bits_accuracy.md。固定设置：d、向量对数、随机种子、G；唯一自变量为 b。

---

[Judge]

Look at `./summary_bits_accuracy.md`, check whether conclusion cover the following points

1. 估计误差随 b 增大而下降。
2. 误差量级符合 O(1/√b)（减半误差需约 4 倍位数）。
3. 估计近似无偏（平均误差接近 0）。


[Judge V2]

查阅 `./summary_bits_accuracy.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；d=100、1000 对、seed=12345、b∈{16,64,256,1024}）：

1. 须给估计误差随 b 增大而下降（golden：RMSE 0.372→0.186→0.097→0.049（b=16→1024）；可接受：随 b 单调降）。（细化原 [Judge] 第 1 点）
2. 须给量级符合 O(1/√b)（golden：RMSE·√b≈常数 1.49–1.57、b→4b 比例 0.499/0.525/0.503≈0.5；可接受：RMSE·√b 近常数且减半需 ~4 倍位数）。（细化原 [Judge] 第 2 点）
3. 须给近似无偏（golden：各 b mean_err +0.0108/−0.0025/+0.0058/−0.0016，|mean_err|≤0.011≪RMSE、符号交替；可接受：|mean_err| ≤ 0.3×RMSE 即视为无偏）。（细化原 [Judge] 第 3 点——给出偏差标尺）

<!-- judge-v2 authored-by: bcb94bc6 -->
