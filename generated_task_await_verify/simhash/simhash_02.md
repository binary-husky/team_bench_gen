[Agents]

读给定材料，做实验，写结论。

考察 SimHash 用汉明距离估计余弦相似度的精度随位数 b 的变化。生成若干对随机向量（d=100 维，约 1000 对，固定随机种子）并已知其余弦相似度；对 b ∈ {16, 64, 256, 1024} 分别用 NumPy 从零实现 SimHash（sketch = sign(G @ v)，G 为 b×d 随机高斯矩阵），由两草图的汉明距离估计余弦角/余弦相似度，计算估计误差（MAE / RMSE）。把「估计误差 随 b 的变化」并与 O(1/√b) 对比，写到 ./summary_bits_accuracy.md。固定设置：d、向量对数、随机种子、G；唯一自变量为 b。

---

[Judge]

Look at `./summary_bits_accuracy.md`, check whether conclusion cover the following points

1. 估计误差随 b 增大而下降。
2. 误差量级符合 O(1/√b)（减半误差需约 4 倍位数）。
3. 估计近似无偏（平均误差接近 0）。
