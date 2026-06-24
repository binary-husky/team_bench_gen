[Agents]

读给定材料，做实验，写结论。

在进程内虚拟 Chord 环（同上，无真实网络）上考察路由对节点失效的鲁棒性。固定 N=1000 节点，每个节点维护长度为 r 的后继列表（successor list）。对 r ∈ {1, 16} 分别：随机失效占比 f ∈ {0, 0.1, 0.2, 0.3, 0.5} 的节点，再用存活节点 + 后继列表发起约 1×10^4 次随机键查找，统计「查找成功率」（正确找到负责该键的存活后继的比例）。把「查找成功率 随 f 的变化，并对比 r=1 与 r=16」写到 ./summary_failure_tolerance.md。固定设置：N=1000、f 取值、查询数、随机种子；自变量为 f 与 r。

---

[Judge]

Look at `./summary_failure_tolerance.md`, check whether conclusion cover the following points

1. 后继列表足够长（r=16）时，查找成功率在 f 高达约 0.5 时仍接近 100%。
2. 无后继列表（r=1）时，成功率随 f 增大急剧下降。
3. 结论指出 Chord 的容错能力来自维护足够长的后继列表以跳过连续失效节点。
