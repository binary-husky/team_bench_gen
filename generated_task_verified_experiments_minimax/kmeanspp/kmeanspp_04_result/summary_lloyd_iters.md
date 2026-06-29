# 收敛所需 Lloyd 迭代数：k-means++ vs random

## 1. 实验设置

| 项 | 值 |
|---|---|
| 数据集 | `sklearn.datasets.make_blobs`，n=5000，d=2，centers=10，cluster_std=1.0，random_state=42（**固定**） |
| k | 10 |
| n_init | 1（自变量仅为 `init`） |
| tol | 1e-4（默认） |
| max_iter | 300 |
| random_state 集合 | 0..29，共 30 个（**仅作用于 KMeans 自身的随机性**） |
| 自变量 | 选种方式 `init ∈ {'k-means++', 'random'}` |
| 测量 | `KMeans(...).n_iter_`（Lloyd 收敛所耗的迭代轮数） |

每个 `init` 在 30 个 `random_state` 上各跑 1 次，共 30×2 = 60 次 KMeans。
代码与原始数据见同目录 `experiment.py` 与 `lloyd_iters_raw.json`。

## 2. 结果

| init | 30 次运行的 n_iter | 均值 | 标准差 (ddof=1) | 最小 | 中位数 | 最大（最差） |
|---|---|---:|---:|---:|---:|---:|
| **k-means++** | 见下 | **8.57** | **3.34** | 4 | 7.5 | **16** |
| random       | 见下 | 10.57 | 3.52 | 6 | 10.5 | 21 |

- **k-means++ 的 30 个 n_iter**：8, 13, 8, 5, 16, 11, 6, 8, 6, 6, 6, 16, 7, 6, 7, 12, 5, 9, 6, 9, 5, 13, 7, 6, 10, 14, 10, 11, 4, 7
- **random 的 30 个 n_iter**：8, 11, 21, 6, 7, 11, 10, 12, 8, 6, 11, 11, 15, 9, 9, 14, 15, 14, 12, 10, 8, 7, 8, 7, 11, 18, 11, 11, 9, 7

## 3. 结论

1. **平均迭代数更少**：k-means++ 的均值 (8.57) 比 random (10.57) 少 **2.0 轮**，约 19% 的差距。
2. **更稳定**：k-means++ 的样本标准差 3.34 略小于 random 的 3.52；中位数 7.5 vs 10.5，也明显更低。random 偶发拖到 18、21 轮的尾部，k-means++ 没有出现这种情况。
3. **最差值更小**：k-means++ 的最差一轮为 **16** 轮，random 的最差一轮为 **21** 轮，相差 5 轮。
4. **物理解读**：random 初始化常常把多个中心落到同一真实簇附近，初始势能 φ 远高于 k-means++ 的 D² 采样，势能越高 → 越多的 Lloyd 步才能让 φ 单调下降到稳定点；与 Arthur & Vassilvitskii (2007) 给出的 E[φ] ≤ 8(ln k + 2) φ_OPT 的 O(log k)-competitive 界一致 —— k-means++ 给出的初始解更接近 φ_OPT，因而后续 EM-style 迭代也更短。

> 一句话：**同样的 30 个 random_state、n_init=1，k-means++ 在平均、标准差与最差值上均优于 random 初始化**（均 8.57 vs 10.57；std 3.34 vs 3.52；max 16 vs 21）。
