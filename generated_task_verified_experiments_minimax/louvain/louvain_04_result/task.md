[Agents]

读给定材料，做实验，写结论。

考察 Louvain 检测社区与「已知真实社区」的吻合度如何随社区结构强度（混合参数 μ）变化。数据：LFR 基准图，μ ∈ {0.1, 0.3, 0.5, 0.7}，其余固定（n=1000, tau1=3, tau2=1.5, average_degree=6, min_community=20, seed=0）；LFR 图自带真实社区标签（节点属性 'community'）。方法：对每个图运行 Louvain（best_partition(G, random_state=0)），把检测结果与真实标签用 NMI（sklearn.metrics.normalized_mutual_info_score）与 ARI（sklearn.metrics.adjusted_rand_score）比较；同时记录模块度 Q。把「NMI、ARI、Q 随 μ 的变化」写到 ./summary_accuracy.md。固定设置：上述 LFR 参数与随机种子；唯一自变量为 μ。

---

[Judge]

Look at `./summary_accuracy.md`, check whether conclusion cover the following points

1. μ 较小（如 0.1）时 NMI/ARI 很高（接近 1，社区结构清晰，几乎完全恢复真实社区）。
2. 当 μ 超过约 0.5 后 NMI/ARI 急剧下降（社区结构模糊，检测质量骤降）。
3. 模块度 Q 也随 μ 增大而下降，但下降比 NMI 平缓。


[Judge V2]

查阅 `./summary_accuracy.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；LFR 固定/seed=0、自变量 μ）：

1. 须给 μ 小时 NMI/ARI 高近 1（golden：μ=0.1 NMI≈0.98/ARI≈0.93、检出 35 vs 真实 34；可接受：μ=0.1 NMI≥0.9）。（细化原 [Judge] 第 1 点）
2. 须给 μ>0.5 后 NMI/ARI 急降（golden：μ=0.3 NMI≈0.42、μ=0.7 NMI≈0.19/ARI≈0.02；可接受：μ=0.7 NMI≤0.3）。（细化原 [Judge] 第 2 点）
3. 须给 Q 下降但比 NMI 平缓（golden：Q 0.90→0.51、μ=0.7 仍 Q≈0.51（伪社区）；可接受：Q 降幅 < NMI 降幅）。（细化原 [Judge] 第 3 点——补 Q 高≠吻合的局限）

<!-- judge-v2 authored-by: bcb94bc6 -->
