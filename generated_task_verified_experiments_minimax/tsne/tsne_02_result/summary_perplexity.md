# t-SNE 困惑度（Perplexity）影响的实验结论

## 任务与设置

- 数据集：`sklearn.datasets.load_digits`（1797 个样本、64 维、10 类，0–9 手写数字）。
- 自变量：`perplexity ∈ {5, 15, 30, 50, 100, 200}`。
- 固定超参数：`n_components=2, init='pca', learning_rate='auto', max_iter=1000, random_state=0`，其余为 sklearn 默认。
- 评估指标：
  - `sklearn.metrics.silhouette_score(X_embedded, y, metric='euclidean')`：二维嵌入按数字标签的轮廓系数，越大表示按类别分簇越清晰。
  - `sklearn.manifold.trustworthiness(X, X_embedded, n_neighbors=12)`：12 邻域尺度下的可信度，越接近 1 表示高维局部邻域结构在低维中保留得越好。

## 实验结果

| perplexity | silhouette_score | trustworthiness (n_neighbors=12) | runtime (s) |
|------------|------------------|---------------------------------|-------------|
| 5          | 0.428292         | 0.989506                        | 1.23        |
| 15         | 0.554608         | 0.991340                        | 1.49        |
| 30         | 0.555729         | 0.991732                        | 1.28        |
| **50**     | **0.556644**     | 0.991070                        | 1.42        |
| 100        | 0.519787         | 0.989955                        | 2.29        |
| 200        | 0.483608         | 0.988200                        | 3.15        |

（脚本 `run_experiment.py`，CPU 运行时间；单次 1000 迭代，总耗时在数秒量级。）

## 结论：哪个 perplexity 最优

**最优点：`perplexity = 50`**。

- 在轮廓系数（silhouette_score）维度上，`perplexity=50` 取得最大值 0.556644；继续增大到 100、200 时显著下降（→0.520 / 0.484）。这说明太小的 `perplexity=5` 严重欠拟合高维邻域（0.428），太大的 `perplexity` 又会把过多非邻域点拉入局部概率分布，模糊了类别边界。
- 在可信度（trustworthiness, n_neighbors=12）维度上，`perplexity=30` 最高（0.991732），但 `perplexity=50` 紧随其后（0.991070），差距仅约 0.0007；15、30、50 三档几乎并列，且都明显高于 5、100、200。
- 综合来看，`perplexity ∈ [30, 50]` 是本数据集上的最优平台区；二者取最大者，`perplexity=50` 是综合最优解。该结论也与 van der Maaten & Hinton (2008) 原文给出的经验区间（"typical values are between 5 and 50"）一致——本数据集中更靠近区间上界。
- 工程上附带观察：在 `digits` 这种 10 类、近邻结构丰富的数据集上，`perplexity` 在 15–50 之间是稳定且鲁棒的；如果计算资源紧张，`perplexity=30` 提供了几乎等价的 trustworthiness 与略低的 silhouette，但运行时更短。

## 复现说明

- 运行命令：`python3 run_experiment.py`
- 输出表格打印至标准输出，并写入 `results.json`，便于核对。
- 随机性：固定 `random_state=0`，结果可重复。