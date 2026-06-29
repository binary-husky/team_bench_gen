[Agents]

读给定材料，做实验，写结论。

考察数据分布对 Space-Saving 效果的影响。生成两条 N=1×10^6 的流：一条 Zipfian 强偏斜、一条均匀分布（相同基数、固定种子）。对两条流分别运行 Space-Saving（k=100），以全量精确计数为基准，比较 top-k 的 precision@k 与 recall@k。把「Zipfian vs 均匀 两条流下 precision/recall 的对比」写到 ./summary_skew_vs_uniform.md。固定设置：N、k、基数、随机种子；自变量为数据分布。

---

[Judge]

Look at `./summary_skew_vs_uniform.md`, check whether conclusion cover the following points

1. Zipfian（偏斜）流上 precision/recall 很高（少数重击点能塞进 k 个槽）。
2. 均匀流上 precision/recall 明显变差（无重击点、大量元素竞争、top-k 模糊）。
3. 结论指出 Space-Saving 在偏斜流（真实世界常见）上表现远优于均匀流。


[Judge V2]

查阅 `./summary_skew_vs_uniform.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；k=100、Zipfian vs Uniform、N=1e5）：

1. 须给 Zipfian precision/recall 高（golden：0.73、头部完全正确（rank-1 真值 608072 远超驱逐误差 241）、边界附近损失致 0.73；可接受：偏斜下头部 100% 正确、precision ≥0.6）。（细化原 [Judge] 第 1 点——"很高"细化为 0.73 + 头部完美）
2. 须给均匀流 precision/recall 明显变差（golden：0.00（0/100 重叠）、估计严重高估（max 10000 vs 真实 26）；可接受：均匀 ≪偏斜）。（细化原 [Judge] 第 2 点）
3. 须给偏斜流远优于均匀流（golden：0.73 vs 0.00；可接受：偏斜 >均匀）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
