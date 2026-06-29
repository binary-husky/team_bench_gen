[Agents]

读给定材料，做实验，写结论。

考察计数器槽数 k 对准确度与内存的影响。在同一条 Zipfian 流（N=1×10^6，固定种子）上，对 k ∈ {50, 100, 200, 500} 分别运行 Space-Saving，以全量精确计数为基准。记录每个 k 下的 precision@k、recall@k、最大频率高估误差，以及占用槽位数（内存）。把「precision/recall、最大误差、内存 随 k 的变化」写到 ./summary_slots_k.md。固定设置：N、Zipfian 参数、随机种子；唯一自变量为 k。

---

[Judge]

Look at `./summary_slots_k.md`, check whether conclusion cover the following points

1. k 越大，precision/recall 越高（漏检更少）。
2. 最大高估误差界 N/k 随 k 增大而收紧（误差下降）。
3. 内存（槽位数）随 k 线性增长。


[Judge V2]

查阅 `./summary_slots_k.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；Space-Saving、自变量 k、Zipfian）：

1. 须给 k 越大 precision/recall 越高（漏检更少）（golden：k=50→500 precision/recall 单调升；可接受：随 k 升）。（细化原 [Judge] 第 1 点）
2. 须给最大高估误差界 N/k 随 k 收紧（golden：最大高估 5537→1970→700→176（k=50→500）、约 k^-1.4 衰减、每翻倍 k 误差 ~1/2.8、恒 ≤N/k；可接受：误差随 k 降且 ≤N/k）。（细化原 [Judge] 第 2 点）
3. 须给内存(槽位数)随 k 线性（golden：slots=k、~16 B/槽；可接受：内存 ∝k）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
