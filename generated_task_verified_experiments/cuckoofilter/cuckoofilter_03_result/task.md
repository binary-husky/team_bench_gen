[Agents]

读给定材料，做实验，写结论。

考察 bucket 大小 b 对最大负载因子与踢出（kick）行为的影响。用上述自实现 cuckoo filter（同 partial-key 规则），固定 bucket 数 M。对 b ∈ {2, 4, 8} 分别：持续插入随机键，直到某次插入的连续踢出次数超过上限（如 500 次）而判定 filter 已满（插入失败），记录此时达到的负载因子（已占用槽 / 总槽），以及此前每次成功插入的平均踢出次数。把「最大负载因子、平均踢出次数 随 b 的变化」写到 ./summary_load_vs_b.md。固定设置：M、踢出上限、随机种子；唯一自变量为 b。

---

[Judge]

Look at `./summary_load_vs_b.md`, check whether conclusion cover the following points

1. bucket 越大，可达负载因子越高（如 b=2 约 0.84、b=4 约 0.95）。
2. 平均踢出次数在远离上限时较低，接近上限时上升。
3. 插入失败发生在接近理论最大负载处。
