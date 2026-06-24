[Agents]

读给定材料，做实验，写结论。

考察计数器槽数 k 对准确度与内存的影响。在同一条 Zipfian 流（N=1×10^6，固定种子）上，对 k ∈ {50, 100, 200, 500} 分别运行 Space-Saving，以全量精确计数为基准。记录每个 k 下的 precision@k、recall@k、最大频率高估误差，以及占用槽位数（内存）。把「precision/recall、最大误差、内存 随 k 的变化」写到 ./summary_slots_k.md。固定设置：N、Zipfian 参数、随机种子；唯一自变量为 k。

---

[Judge]

Look at `./summary_slots_k.md`, check whether conclusion cover the following points

1. k 越大，precision/recall 越高（漏检更少）。
2. 最大高估误差界 N/k 随 k 增大而收紧（误差下降）。
3. 内存（槽位数）随 k 线性增长。
