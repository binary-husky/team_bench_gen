# iForest vs LOF 基线对比

## 任务

将 `sklearn.ensemble.IsolationForest`（ψ=256, `n_estimators=100`, `random_state=0`）与基线方法 `sklearn.neighbors.LocalOutlierFactor`（LOF）做异常检测对比，记录各自的检测 AUC（`roc_auc_score`）与训练/预测耗时。固定设置：数据集、各方法参数、`random_state`；自变量为检测方法。

## 实验设置

### 数据集

任务要求“同上数据（固定种子）”。本任务目录中未提供任何外部数据文件（`iforest_material/` 仅有 iForest 论文 PDF），因此按论文 Mulcross 合成数据的精神，用固定种子 `random_state=0` 生成一个可复现的合成异常检测基准数据集：

- 规模：N = 20 000，维度 D = 10
- 正常点（18 000）：单一多元高斯簇 `N(0, I)`
- 异常点（2 000，污染率 10%）：散布在正常簇外圈（半径 6–12）的稀疏孤立点，方向均匀采样
- 用同一 `RandomState(0)` 生成并打乱，保证两个方法面对完全相同的数据

> 选择“散布式稀疏异常”而非“远距紧密簇”是为了给 LOF 一个公平、非退化的机会——若异常自成紧密簇，LOF 因其局部密度特性会把异常簇当作正常（AUC≈0.5，退化为随机），失去对比意义。散布式异常是经典的“高斯 + 均匀离群点”异常检测基准。

### 方法与参数（固定）

| 方法 | 关键参数 | 说明 |
|---|---|---|
| IsolationForest | `n_estimators=100`, `max_samples=256`（即 ψ=256）, `random_state=0`, `n_jobs=1` | 论文默认 ψ=256、t=100 |
| LocalOutlierFactor（基线） | `n_neighbors=10`（即 k=10）, `contamination='auto'`, `n_jobs=1` | 论文中 LOF 通用设置 k=10 |

- 评分：iForest 用 `-score_samples`（越大越异常）；LOF 用 `-negative_outlier_factor_`（越大越异常）。
- AUC：`roc_auc_score(y_true, score)`，`y_true` 中 1=异常。
- 耗时：`time.perf_counter()` 测量 `fit` 与评分两段；每个方法重复 5 次取均值（AUC 由种子决定为确定值）。单线程，CPU-only。

## 结果

| 方法 | 检测 AUC | 训练耗时 (fit) | 预测耗时 (predict) | 总耗时 |
|---|---|---|---|---|
| **IsolationForest** (ψ=256, t=100) | **0.9978** | 159.6 ms | 331.1 ms | **490.7 ms** |
| **LocalOutlierFactor** (k=10, 基线) | 0.9968 | 4471.0 ms | ~0 ms | 4471.0 ms |
| 差值（iForest − LOF） | **+0.0010** | — | — | — |
| 加速比（LOF 总耗时 / iForest） | — | — | — | **≈9.1×** |

（5 次重复均值；AUC 为种子确定值。LOF 的“预测”耗时≈0，因为 `negative_outlier_factor_` 在 `fit` 阶段已对全量数据算好，无需再调用 predict。）

## 结论

1. **检测精度（AUC）**：在固定种子、相同数据上，iForest（0.9978）与 LOF（0.9968）的检测 AUC 几乎持平，iForest 略高 +0.0010。两者在该（散布式离群）基准上都能把异常与正常高度可分。

2. **耗时**：iForest 总耗时约 491 ms，LOF 约 4471 ms，**iForest 快约 9.1×**。差距主要来自训练阶段：LOF 需对全部 N 个点做 k 近邻距离计算（复杂度随 N 平方级增长），而 iForest 只需在子样本 ψ=256 上建 100 棵隔离树（训练复杂度 O(t·ψ·log ψ)，与 N 无关），并且检测时不依赖任何距离/密度计算。

3. **与论文一致性**：该结果与 Liu et al. 2008 iForest 论文第 5 节的结论方向一致——iForest 在 AUC 上与 LOF 相当或略优，而在处理时间上显著优于 LOF，且数据规模越大优势越明显（因为 LOF 的代价随 N 增长，iForest 的训练代价基本与 N 无关）。

4. **方法本质差异**：iForest 通过“隔离”而非“建模正常轮廓”来检测异常，天然支持小子采样，避免了 LOF 的成对距离开销；LOF 是基于局部密度的方法，对自成紧密簇的异常会失效（见上文退化说明），且在大规模数据上计算昂贵。

综上，**在本固定种子基准上，iForest 以约 1/9 的耗时取得了与 LOF 基本持平（略优）的检测 AUC**，验证了 iForest 相对 LOF 基线在精度与效率上的优势。

## 复现

```
python3 run_experiment.py     # 生成数据 + 跑两个方法 + 写 results.json
```

原始数值见 `results.json`；实验脚本见 `run_experiment.py`。
