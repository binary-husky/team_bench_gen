[Agents]

读给定材料，做实验，写结论。

在等量内存预算下对比 cuckoo filter 与 Bloom filter。固定键集大小 N=2×10^5 与内存预算 B 比特：配置 cuckoo filter（选取 f、b=4、M 使总内存约 B 比特）与 Bloom filter（m=B 比特、最优 k=(m/N)·ln2）。把同一组 N 个键分别插入两者；用 N 个非成员键查询，记录各自的 FPR；并测量两者的插入与查询吞吐（ops/秒）。把「FPR、吞吐 的 cuckoo vs Bloom 对比」以及「是否支持删除」写到 ./summary_cuckoo_vs_bloom.md。固定设置：N、B、cuckoo 的 (f,b,M)、Bloom 的 (m,k)、随机种子；自变量为过滤器类型。

---

[Judge]

Look at `./summary_cuckoo_vs_bloom.md`, check whether conclusion cover the following points

1. 等内存预算下，cuckoo 的 FPR 不高于（通常低于）Bloom（中等目标 FPR 区间）。
2. 二者吞吐都很高（同为 O(1) 量级；cuckoo 因哈希次数更少而查询吞吐相当或更高）。
3. cuckoo filter 额外支持删除，标准 Bloom 不支持。


[Judge V2]

查阅 `./summary_cuckoo_vs_bloom.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；N=2×10⁵、B=10.526 bits/item、~0.7% FPR 区间、5 种子）：

1. **重写/放宽原 [Judge] 第 1 点**：原判"cuckoo FPR 不高于 Bloom"在 ~0.7% FPR 工作点不成立——golden：cuckoo 0.739% vs Bloom 0.638%（cuckoo 为 Bloom 1.16×，略高）；放宽为"cuckoo FPR 与 Bloom 同量级（≤1.2× Bloom）"，并指出需 semi-sort cuckoo 才在 ε<3% 反超。可接受：cuckoo/Bloom FPR 比 ∈[0.9,1.2] 且能解释 semi-sort 条件。（重写/放宽原 [Judge] 第 1 点）
2. **放宽原 [Judge] 第 2 点**：原判"cuckoo 查询吞吐相当或更高"仅在正查询成立——golden：正查询 cuckoo 756k > Bloom 625k、负查询 cuckoo 548k < Bloom 857k；放宽为"区分正/负：正查询 cuckoo ≥ Bloom、负查询 cuckoo ≤ Bloom（均 O(1)）"。可接受：正查询 cuckoo≥Bloom、负查询 cuckoo<Bloom、均 O(1) 量级。（放宽原 [Judge] 第 2 点）
3. 须给 cuckoo 支持删除、标准 Bloom 不支持（golden：cuckoo 可删、Bloom 不可；可接受：明确指出此差异）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
