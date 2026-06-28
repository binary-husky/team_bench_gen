[Agents]

读给定材料，做实验，写结论。

在等量内存预算下对比 cuckoo filter 与 Bloom filter。固定键集大小 N=2×10^5 与内存预算 B 比特：配置 cuckoo filter（选取 f、b=4、M 使总内存约 B 比特）与 Bloom filter（m=B 比特、最优 k=(m/N)·ln2）。把同一组 N 个键分别插入两者；用 N 个非成员键查询，记录各自的 FPR；并测量两者的插入与查询吞吐（ops/秒）。把「FPR、吞吐 的 cuckoo vs Bloom 对比」以及「是否支持删除」写到 ./summary_cuckoo_vs_bloom.md。固定设置：N、B、cuckoo 的 (f,b,M)、Bloom 的 (m,k)、随机种子；自变量为过滤器类型。

---

[Judge]

Look at `./summary_cuckoo_vs_bloom.md`, check whether conclusion cover the following points

1. 等内存预算下，cuckoo 的 FPR 不高于（通常低于）Bloom（中等目标 FPR 区间）。
2. 二者吞吐都很高（同为 O(1) 量级；cuckoo 因哈希次数更少而查询吞吐相当或更高）。
3. cuckoo filter 额外支持删除，标准 Bloom 不支持。
