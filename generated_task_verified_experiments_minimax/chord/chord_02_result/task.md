[Agents]

读给定材料，做实验，写结论。

在进程内用 Python 实现一个虚拟 Chord 环仿真（节点为对象、路由表为数据、查询为内存跳数；不使用真实网络/socket/Docker）。考察查找路径长度随节点数 N 的变化。m 位标识符（m 取足够大，如用 SHA-1 取 m=160，或 m=ceil(log2(N))+10），节点 ID 与键 ID 由哈希确定；每个节点构建完整 finger table。对 N ∈ {100, 200, 500, 1000, 2000}，各随机加入 N 个节点，再发起约 1×10^4 个随机键的 find_successor 查询（固定随机种子），用 finger-table 路由协议逐跳转发，记录每次查询的跳数。计算每个 N 下的平均跳数与最大跳数。把「平均跳数、最大跳数 随 N 的变化，并与 log2(N) 对比」写到 ./summary_lookup_hops.md。固定设置：m、查询数、随机种子、路由协议；唯一自变量为 N。

---

[Judge]

Look at `./summary_lookup_hops.md`, check whether conclusion cover the following points

1. 平均跳数随 N 对数增长（约为 ½·log2(N) 量级）。
2. 最大跳数被 O(log N) 上界约束（≤约 log2(N)）。
3. 整体确认查找复杂度为 O(log N)（随 log N 线性、而非随 N 线性）。

---

[Judge V2]

查阅 `./summary_lookup_hops.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准）：

1. 须给平均跳数随 N 对数增长追踪 ½·log₂N（golden：3.22/3.70/4.34/4.80/5.36、比值 0.96–0.98；可接受：比值 ∈[0.85,1.05] 且 N×20 增 ≤2.5 跳）。（细化原 [Judge] 第 1 点）
2. 须给最大跳数 O(log N)（golden：7/8/9/11/10 ≤ log₂N；可接受：max ≤ log₂N+1）。（细化原 [Judge] 第 2 点）
3. 须给整体 O(log N) + 正确性（golden：5 万查询 0 错配；可接受：错配率 0）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
