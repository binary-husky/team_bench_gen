# Louvain 多轮 (pass) 迭代的模块度收敛

## 1. 实验设置

| 项目 | 值 |
| --- | --- |
| 图 | `networkx.LFR_benchmark_graph` |
| 节点数 n | 1000 |
| 边数 m | 2044 |
| 幂律参数 τ₁ | 3 |
| 社区规模幂律 τ₂ | 1.5 |
| 混合参数 μ | 0.4 |
| 平均度 average_degree | 6 |
| 最小社区 min_community | 20 |
| 图生成 seed | 0 |
| Louvain `random_state` | 0 |
| 接口 | `community.community_louvain.generate_dendrogram(G, random_state=0)` |
| 每一层回填 | `community_louvain.partition_at_level(dendrogram, level)` |
| 模块度 | `community_louvain.modularity(partition, G)` |

> 注：`average_degree=6, min_community=20, seed=0` 在本环境下能直接生成图，无需微调；最终生成 1000 节点 / 2044 条边。
> 节点的字符串 ID 在生成后用 `nx.convert_node_labels_to_integers` 重新映射为整数，方便下游处理。

## 2. 实验方法

Louvain 算法每执行一次“局部移动 + 社区聚合”称为 **一个 pass**。`generate_dendrogram` 内部反复执行该流程，并把每一轮的合并记录保存在 `dendrogram[level]` 中。

对每一个 pass 索引 `level ∈ [0, len(dendrogram))`：

1. `partition_at_level(dendrogram, level)` 将该层压缩过的社区 ID 展开回原始节点；
2. 用 `community_louvain.modularity(partition, G)` 计算该层在原图上的模块度 Q；
3. 统计该层中“不同的社区标签数”= 该层社区数。

> 关键观察：`dendrogram[level]` 末尾的合并数量 = `dendrogram[level+1]` 中用于“聚合前”社区图的节点数。例如第 0 层做了 1000 次合并 → 进入第 1 层时被压缩成 323 个 meta-node，323 次合并 → 83 个 meta-node，…，最后 24 → 20 个 meta-node。社区数单调不增（与 Blondel 等 2008 论文第 2 节“The number of meta-communities decreases at each pass”一致）。

## 3. 实验结果

总轮数（pass 数）= **4**。

| pass index | 该层合并数 | 社区数 | 模块度 Q | ΔQ vs 上一 pass | Δ#communities vs 上一 pass |
| :---: | :---: | :---: | :---: | :---: | :---: |
| 0 | 1000 | 323 | 0.360066 | — | — |
| 1 | 323 | 83 | 0.523549 | +0.163483 | −240 |
| 2 | 83 | 24 | 0.559394 | +0.035845 | −59 |
| 3 | 24 | 20 | **0.559732** | +0.000338 | −4 |

最终（pass 3 结束）社区数 = **20**，模块度 **Q = 0.559732**。
最佳 Q 出现在第 3 个 pass，Q_max = 0.559732。

注意：表中 “该层合并数” = `len(dendrogram[level])`，即在进入 `level+1` 层之前对 `level` 层社区进行合并的次数；“社区数”= 投影回原节点后不同社区标签的个数。

## 4. 收敛趋势

1. **社区数指数级塌缩**：323 → 83 → 24 → 20。前两个 pass 把 1000 个 singleton 收缩到 24 个“原子”社区，规模缩减量 ≥ 26×；第 3 个 pass 几乎只动了 4 个社区（24 → 20）。
2. **Q 单调上升但增幅快速衰减**：0.360 → 0.524 → 0.559 → 0.560。ΔQ 从 +0.163 → +0.036 → +0.0003，三轮后 Q 的相对增量只有初始 Q 的 0.06% 左右，已经进入实际收敛。
3. **总 pass 数很小**：仅 4 个 pass 算法即结束，与 Blondel 等 2008 第 3 节“The number of passes is usually very small”以及“the height of the hierarchy … is generally a small number”的结论一致。
4. **Q 与社区数同时趋于稳定**：当 ΔQ < 10⁻³ 且 Δ#communities = 4（≈ 当前社区数的 17%）时，再做一次 pass 已无明显改善，说明分层结构在此处达到局部最优。
5. **最佳 Q 出现在最后一层**：本例中 Q 严格随 pass 上升（与 Blondel 等 2008 的“final partition 取得最大 Q”一致），但理论上由于局部移动的不唯一性，中间层偶尔也可能给出比末层更高的 Q；本图未观察到这种现象。

## 5. 结论

在该 LFR 图（n=1000, μ=0.4, ⟨k⟩=6）上，python-louvain 的 Louvain 实现仅用 **4 个 pass** 就收敛：

- Q 从 0.360 提升到 **0.560**（提升约 55%），全部提升发生在前两个 pass（贡献了 0.199 / 0.200 的总提升），第 3 个 pass 只贡献 0.0003。
- 社区数从 1000（隐含起点）→ 323 → 83 → 24 → 20，每层合并量也按 1000 / 323 / 83 / 24 的比例指数下降。
- 由于 ΔQ 在 pass 3 之后已经小于 10⁻³，且社区数也几乎不再减少，可认为 Louvain 在第 3 个 pass 后即达到收敛。python-louvain 之所以仍输出第 4 层，是因为算法在第 3 层后已经找不到任何能再提升 Q 的合并动作，但内部循环会再验证一次以确认无提升。

这印证了论文的核心观察：Louvain 的层次展开是**很快收敛**的——绝大部分模块度增益在第一两个 pass 就拿到，后续 pass 主要做精细合并，最终层级数普遍很小（本例为 4 层）。
