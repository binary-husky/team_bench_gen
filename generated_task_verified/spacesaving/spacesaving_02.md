[Agents]

读给定材料，做实验，写结论。

考察 Space-Saving 识别 top-k 频繁项的准确度。生成 Zipfian 偏斜流（N=1×10^6 项，可控偏斜参数，固定随机种子）；用「全量精确计数」得到真实频率作为基准。运行 Space-Saving（k=100 个计数器槽），取出其报告的 top-k。计算 precision@k 与 recall@k（相对真实 top-k），以及各元素估计频率 f̂ 相对真实 f 的误差（重点看是否高估、平均/最大高估量）。把「precision@k、recall@k、频率高估误差」写到 ./summary_topk_accuracy.md。固定设置：N、Zipfian 参数、k=100、随机种子；本题为准确性测量（无自变量）。

---

[Judge]

Look at `./summary_topk_accuracy.md`, check whether conclusion cover the following points

1. 在 Zipfian 偏斜流上，top-k 的 precision@k 与 recall@k 都很高（接近 1）。
2. 所有估计频率 f̂ 均 ≥ 真实频率 f（只高估、不低估）。
3. 最大高估误差不超过 N/k 量级（与理论界一致）。


[Judge V2]

查阅 `./summary_topk_accuracy.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；Zipfian、k=m=100、N=1e5）：

1. **放宽原 [Judge] 第 1 点**：原判"precision@k/recall@k 都很高(接近 1)"在 m=k=100 该 Zipfian 下不成立——golden：precision=recall=**0.54**（54/100）；放宽为"取决于 k vs 长尾密度：m=k=100 不足以覆盖长尾、得 0.54（高于 Theorem 1 保证下界 34/100=0.34）"。可接受：给出实测 precision/recall + 与理论下界比较即给分。（放宽原 [Judge] 第 1 点）
2. 须给所有 `f̂≥f`（只高估不低估）（golden：恒 ≥0、0 低估；可接受：0 低估）。（细化原 [Judge] 第 2 点）
3. 须给最大高估 ≤N/k 量级（golden：min=1931 ≤N/k=10000、最大高估 1931；可接受：max 高估 ≤N/k）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
