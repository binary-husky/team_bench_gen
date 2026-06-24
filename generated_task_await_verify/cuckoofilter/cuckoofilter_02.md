[Agents]

读给定材料，做实验，写结论。

考察指纹位数 f 对误判率（false-positive rate, FPR）的影响。用 Python 从零实现一个 cuckoo filter（或用 py-cuckoofilter），支持配置 fingerprint 位数 f、bucket 大小 b、bucket 数 M；partial-key cuckoo hashing：i1 = hash(key)、fingerprint f = fp(key)（非零）、i2 = i1 ⊕ hash(f)。固定 bucket 大小 b=4，bucket 数 M 取足够大以容纳目标键数并保持高负载。插入 N=2×10^5 个键（如整数 0..N−1），再用 N 个非成员键（N..2N−1）查询，统计 FPR。对 f ∈ {4, 8, 12, 16} 各做若干随机种子取平均。把「FPR 随 f 的变化」并与理论值 2b·load/2^f 对比，写到 ./summary_fpr_vs_f.md。固定设置：b=4、M、N、随机种子；唯一自变量为 f。

---

[Judge]

Look at `./summary_fpr_vs_f.md`, check whether conclusion cover the following points

1. FPR 随 f 增大而（近似）指数下降。
2. 实测 FPR 与理论 2b·load/2^f 在量级上吻合。
3. f 每增加 1 位，FPR 约下降一半。
