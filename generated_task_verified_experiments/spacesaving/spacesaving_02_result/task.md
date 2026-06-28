[Agents]

读给定材料，做实验，写结论。

考察 Space-Saving 识别 top-k 频繁项的准确度。生成 Zipfian 偏斜流（N=1×10^6 项，可控偏斜参数，固定随机种子）；用「全量精确计数」得到真实频率作为基准。运行 Space-Saving（k=100 个计数器槽），取出其报告的 top-k。计算 precision@k 与 recall@k（相对真实 top-k），以及各元素估计频率 f̂ 相对真实 f 的误差（重点看是否高估、平均/最大高估量）。把「precision@k、recall@k、频率高估误差」写到 ./summary_topk_accuracy.md。固定设置：N、Zipfian 参数、k=100、随机种子；本题为准确性测量（无自变量）。

---

[Judge]

Look at `./summary_topk_accuracy.md`, check whether conclusion cover the following points

1. 在 Zipfian 偏斜流上，top-k 的 precision@k 与 recall@k 都很高（接近 1）。
2. 所有估计频率 f̂ 均 ≥ 真实频率 f（只高估、不低估）。
3. 最大高估误差不超过 N/k 量级（与理论界一致）。
