[Agents]

读给定材料，做实验，写结论。

考察数据分布对 Space-Saving 效果的影响。生成两条 N=1×10^6 的流：一条 Zipfian 强偏斜、一条均匀分布（相同基数、固定种子）。对两条流分别运行 Space-Saving（k=100），以全量精确计数为基准，比较 top-k 的 precision@k 与 recall@k。把「Zipfian vs 均匀 两条流下 precision/recall 的对比」写到 ./summary_skew_vs_uniform.md。固定设置：N、k、基数、随机种子；自变量为数据分布。

---

[Judge]

Look at `./summary_skew_vs_uniform.md`, check whether conclusion cover the following points

1. Zipfian（偏斜）流上 precision/recall 很高（少数重击点能塞进 k 个槽）。
2. 均匀流上 precision/recall 明显变差（无重击点、大量元素竞争、top-k 模糊）。
3. 结论指出 Space-Saving 在偏斜流（真实世界常见）上表现远优于均匀流。
