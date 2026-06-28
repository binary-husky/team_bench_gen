[Agents]

读给定材料，做实验，写结论。

考察 bucket 大小 b 对最大负载因子与踢出（kick）行为的影响。用上述自实现 cuckoo filter（同 partial-key 规则），固定 bucket 数 M。对 b ∈ {2, 4, 8} 分别：持续插入随机键，直到某次插入的连续踢出次数超过上限（如 500 次）而判定 filter 已满（插入失败），记录此时达到的负载因子（已占用槽 / 总槽），以及此前每次成功插入的平均踢出次数。把「最大负载因子、平均踢出次数 随 b 的变化」写到 ./summary_load_vs_b.md。固定设置：M、踢出上限、随机种子；唯一自变量为 b。

---

[Judge]

Look at `./summary_load_vs_b.md`, check whether conclusion cover the following points

1. bucket 越大，可达负载因子越高（如 b=2 约 0.84、b=4 约 0.95）。
2. 平均踢出次数在远离上限时较低，接近上限时上升。
3. 插入失败发生在接近理论最大负载处。


[Judge V2]

查阅 `./summary_load_vs_b.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；M=2¹⁴、16-bit fp、MaxKicks=500）：

1. 须给 b 越大负载因子越高（golden：b=2→0.877、b=4→0.967、b=8→0.992（5 种子 0.868–0.992）；可接受：b=4 ≥0.95 且单调增）。原 [Judge] 估"b=2 约 0.84"实测 0.877——细化修正。（细化原 [Judge] 第 1 点）
2. 须给平均踢出次数随 b 降、近上限时上升（golden：b=2→1.97、b=4→1.72、b=8→1.19；可接受：大 b 踢出少、近上限上升的趋势正确）。（细化原 [Judge] 第 2 点）
3. 须给插入失败发生在接近理论最大负载处（golden：b=4 ~0.967、b=8 ~0.992 处判满；可接受：失败时负载 ≥0.85）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
