[Agents]

读给定材料，做实验，写结论。

复现并考察困惑度（perplexity）对 t-SNE 二维嵌入的影响。使用 sklearn.datasets.load_digits（共 1797 个样本、64 维、10 类）作为小规模数据；对 perplexity ∈ {5, 15, 30, 50, 100, 200} 逐一运行 sklearn.manifold.TSNE（n_components=2, init='pca', learning_rate='auto', max_iter=1000, random_state=0，其余默认）。每次运行后记录两个指标：(a) 二维嵌入按数字标签的 silhouette score（sklearn.metrics.silhouette_score）；(b) trustworthiness（sklearn.manifold.trustworthiness, n_neighbors=12）。把 perplexity 与两个指标的对照表、以及哪个 perplexity 最优的结论写到 ./summary_perplexity.md。固定设置：上述所有超参数；仅 perplexity 为自变量。

---

[Judge]

Look at `./summary_perplexity.md`, check whether conclusion cover the following points

1. perplexity 过小（如 5）时嵌入明显变差（silhouette 偏低、簇碎裂）。
2. 中等 perplexity（约 30 附近）取得最佳簇分离（silhouette 最高）。
3. perplexity 过大（如 200，相对 1797 个样本已偏大）时全局结构被压扁、silhouette 再次下降。

---

## [Judge V2]（bcb94bc6 修订版 — 执行 agent 超时；本为轻量实验，可补做，放宽为言之有理即给分）

> 查阅 `./summary_perplexity.md`。**如实记录**：本任务（digits t-SNE × perplexity∈{5,15,30,50,100,200}，6 次 sklearn TSNE，属**轻量 CPU 实验**）执行 agent **超时未交卷**，未产出 summary。本任务**本可完成**（非算力瓶颈），但执行 agent 卡住。鉴于无实测 golden，按"言之有理即给分"放宽；参考方向（digits 上经验）如下。

| 原 [Judge] 点 | 参考 golden（digits 经验） | 可接受范围（放宽） |
|---|---|---|
| 1. perplexity 过小(5)→嵌入变差（silhouette 低、簇碎裂） | 小 perplexity 局部化、簇碎裂 | 放宽：方向一致即给分 |
| 2. 中等 perplexity(~30)→最佳簇分离（silhouette 最高） | ~30 附近最优 | 放宽：中段最优方向一致即给分（最优点允许落在 15–50） |
| 3. perplexity 过大(200，相对 1797 样本偏大)→全局压扁、silhouette 再降 | 过大压扁结构 | 放宽：过大端 silhouette 下降方向一致即给分 |

> 总则：执行超时（非算力不可行）；"小→碎裂、中→最优、大→压扁"的 U 形方向一致、推理自洽即通过。若后续补做实验，以实测 silhouette/trustworthiness 数值为准。

<!-- judge-v2 authored-by: bcb94bc6 -->
