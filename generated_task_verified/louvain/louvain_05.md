[Agents]

读给定材料，做实验，写结论。

考察分辨率参数 γ（resolution）对社区划分粒度的影响。数据：LFR 基准图（n=1000, tau1=3, tau2=1.5, mu=0.4, average_degree=6, min_community=20, seed=0）。方法：分别以 resolution γ ∈ {0.5, 1.0, 1.5, 2.0} 运行 Louvain（best_partition(G, random_state=0, resolution=γ)，或 networkx 的 louvain_communities(G, seed=0, resolution=γ)）。对每个 γ 记录：社区数、平均社区规模、以及用标准（γ=1）公式计算的模块度 Q（便于在同一标准下横向比较）。把「社区数 / 平均规模 / 标准模块度 随 γ 的变化」写到 ./summary_resolution.md。固定设置：上述 LFR 参数与随机种子；唯一自变量为 γ。

---

[Judge]

Look at `./summary_resolution.md`, check whether conclusion cover the following points

1. γ 增大（>1）时社区数增多、平均社区规模变小（划分更细）。
2. γ 减小（<1）时社区数减少、社区变大（发生合并）。
3. 用标准（γ=1）模块度衡量时，γ=1 取得最高值，γ 偏离 1 时标准模块度下降。


[Judge V2]

查阅 `./summary_resolution.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；LFR、γ∈{0.5,1,1.5,2}、networkx vs python-louvain）：

1. 须给 γ 增大(>1) 社区数增多、平均规模变小（golden：networkx γ=0.5/1/1.5/2→社区数 7/20/31/39、平均规模 142.86/50/32.26/25.64；可接受：γ↑社区数↑）。（细化原 [Judge] 第 1 点）
2. 须给 γ 减小(<1) 社区数减少、社区变大（golden：γ=0.5 仅 7 个社区/平均 142.86；可接受：γ↓社区数↓）。（细化原 [Judge] 第 2 点）
3. 须给标准(γ=1)模块度 γ=1 区间最高、偏离 1 下降（golden：γ=0.5 Q=0.1287 最低、γ∈[1,2] Q≈0.25 高且接近（局部搜索致 γ∈[1,2] 略有起伏非严格 γ=1 取峰）；可接受：γ=1 区间 Q 高、γ=0.5 低）。注：python-louvain γ=0.5 给 111 社区为实现 artifact，以 networkx 或 γ≥1 为准。（细化原 [Judge] 第 3 点——补平台 + artifact 说明）

<!-- judge-v2 authored-by: bcb94bc6 -->
