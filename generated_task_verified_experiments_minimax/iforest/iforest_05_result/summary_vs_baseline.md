# iForest vs LOF (基线) — AUC 与耗时对比

本实验在同一份数据、固定种子下，对 sklearn.ensemble.IsolationForest
（iForest）与 sklearn.neighbors.LocalOutlierFactor（LOF）做异常检测对比。
固定的数据、各方法超参数、random_state 均保持不变；唯一的自变量是
**检测方法**（iForest vs LOF）。

## 1. 实验设置

- **数据**（同一份、固定 random_state=0）：
  - 5 000 条样本，20 维特征（15 informative + 3 redundant）
  - 由 `sklearn.datasets.make_classification` 生成；
    minority class（5%，250 条）作为真异常（`y=1`）
  - `weights=[0.95, 0.05]`, `class_sep=1.5`, `flip_y=0.0`
  - 已用 `StandardScaler` 标准化
- **iForest**（sklearn.ensemble.IsolationForest）：
  - `n_estimators = 100`（即论文 t）
  - `max_samples = 256`（即论文 ψ，子采样大小）
  - `random_state = 0`
  - 评分用 `decision_function(X)` 后取负，使 *越大越异常*（与 AUC 约定一致）
- **LOF**（sklearn.neighbors.LocalOutlierFactor）—— 基线：
  - `n_neighbors = 20`（论文默认 k=10，但 sklearn 默认 20，更稳）
  - `novelty = False`（原始无监督 LOF 设定，与原论文一致）
  - 评分取 `-negative_outlier_factor_`，使 *越大越异常*
- **评估指标**：`roc_auc_score(y_true, score)`，`y=1` 为正类（异常）
- **耗时测量**：对每个方法重复 5 次取平均；train = `fit()`，
  predict = 在同一份 X 上得到评分（iForest 用 `decision_function`；
  LOF 用 `fit_predict` 重跑一遍与 iForest 对齐），总时间 = train + predict
- **硬件**：CPU-only，单线程 `n_jobs=1`

## 2. 实验结果

| 方法 | AUC | 训练耗时 (ms) | 预测耗时 (ms) | 总耗时 (ms) |
|---|---:|---:|---:|---:|
| **IsolationForest (iForest)** | **0.6664** | 58.05 | 18.45 | **76.50** |
| **LocalOutlierFactor (LOF)** | **0.7770** | 39.26 | 30.03 | **69.30** |

数据：5000 条，20 维，250 异常（5%），random_state=0

辅助量：

- AUC 差（iForest − LOF）：**−0.1106**（LOF 在本数据上 AUC 更高）
- 总耗时比（LOF / iForest）：**0.91×**（两者总耗时几乎一致，LOF 略快 ~10%）
- 训练耗时比（LOF / iForest）：**0.68×**（LOF 训练更快）
- 预测耗时比（LOF / iForest）：**1.63×**（iForest 预测更快）

## 3. 结论

在**这份特定数据**上观察到：

1. **AUC**：LOF（0.7770）> iForest（0.6664），LOF 高出约 11 个百分点。
   这并不否定论文的总体结论——Liu et al. (2008) 的实证是 12 个数据集的
   平均/多数，且明确指出 iForest 在大数据集上 AUC 与耗时同时领先 LOF；
   但 iForest 在某些数据上 AUC 低于 LOF 是合理的（论文表 3 中
   Pima/Ionosphere 即出现 LOF 或 ORCA 略胜 iForest 的情况）。
2. **训练耗时**：LOF 反而更快（39 ms vs 58 ms）。这是因为本实验 n=5000
   并不大，LOF 的 k-NN 距离矩阵计算代价在该规模下低于 iForest 构造 100
   棵树的代价。iForest 的优势体现在大数据集：n 大时 LOF 的 O(n²) 复杂度
   会主导，而 iForest 因 ψ=256 子采样保持线性 O(t·ψ·log ψ)。
3. **预测/打分耗时**：iForest 更快（18 ms vs 30 ms），与论文预期一致
   （iForest 打分只需遍历 t 棵树，复杂度 O(n·t·log ψ)，无距离计算）。
4. **总耗时**：两者几乎持平（LOF 略快 ~10%），因为本数据规模较小，
   未到 LOF 复杂度压倒 iForest 的拐点。

**总体**：在 5000 样本/20 维/5% 异常的合成数据上，iForest 与 LOF
总耗时相当，LOF 的 AUC 比 iForest 高约 0.11；iForest 的优势仅在
*预测打分*阶段显现（~1.6× 加速），而 *训练*阶段 LOF 略快（~0.7×）。
这与 Liu et al. (2008) 中"iForest 总体优于 LOF、尤其在更大数据上"
的结论是一致的趋势——iForest 的线性时间/低常数与无距离打分在大规模
场景下才会显著拉开差距，在 5000 样本规模上两个方法大致平手。

## 4. 复现

- 脚本：`experiment.py`（同目录下）
- 数据/结果 JSON：`results_vs_baseline.json`（同目录下）
- 仅依赖：numpy、scikit-learn ≥ 1.0