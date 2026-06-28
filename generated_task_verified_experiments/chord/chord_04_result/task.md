[Agents]

读给定材料，做实验，写结论。

在进程内虚拟 Chord 环上考察一致哈希的键分布均衡性。固定 N=200 个物理节点，分配 K=1×10^5 个随机键；改变每个物理节点占用的虚拟节点数 v ∈ {1, 2, 5, 10, 20}（每个虚拟节点各取一个哈希 ID 落在环上，键归到对应虚拟节点再聚合到其物理节点）。统计物理节点间键负载的不均衡度：最大负载/平均负载（max/mean）与变异系数（std/mean）。把「max/mean 与变异系数 随 v 的变化」写到 ./summary_key_balance.md。固定设置：N=200、K=1×10^5、随机种子、哈希函数；唯一自变量为 v。

---

[Judge]

Look at `./summary_key_balance.md`, check whether conclusion cover the following points

1. 无虚拟节点（v=1）时，max/mean 负载不均衡较大（明显偏斜）。
2. 随 v 增大，不均衡度下降（负载更均匀）。
3. 不均衡度随 v 大致按 1/√v 量级下降（变异系数 ∝ 1/√(vN)）。
