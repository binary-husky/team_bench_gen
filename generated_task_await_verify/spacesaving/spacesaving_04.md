[Agents]

读给定材料，做实验，写结论。

验证 Space-Saving 的误差保证。在 Zipfian 流（N=1×10^6，固定种子）上运行 Space-Saving（k=100），逐项断言并统计：(1) 每个被监控元素的估计 f̂ 是否都 ≥ 真实 f（无低估）；(2) 最大高估误差是否 ≤ 当前最小计数器值；(3) 最小计数器是否 ≤ N/k。另外对若干 N 或 k 复跑，确认界随 N/k 收紧。把「三条保证的验证结果（是否全部成立）以及界随 N/k 的变化」写到 ./summary_error_bound.md。固定设置：N、k、Zipfian 参数、随机种子；自变量为（用于界收紧检查的）N 或 k。

---

[Judge]

Look at `./summary_error_bound.md`, check whether conclusion cover the following points

1. 所有被监控元素的估计 f̂ 均 ≥ 真实 f（无任何低估）。
2. 最大高估误差 ≤ 当前最小计数器值（逐项断言成立）。
3. 最小计数器 ≤ N/k（界成立），且随 k 增大 / N 减小而收紧。
