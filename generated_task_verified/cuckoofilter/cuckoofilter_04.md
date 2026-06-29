[Agents]

读给定材料，做实验，写结论。

考察 cuckoo filter 的删除正确性，并对比标准（非计数）Bloom filter。用自实现 cuckoo filter（b=4, f=12）插入 N=1×10^5 个键；随机删除其中一半。然后：查询保留的那一半（应为全部命中，统计假阴性率 false-negative rate），查询被删除的那一半（应为不存在，仅受 FPR 影响），再查一组全新非成员。另外用自实现标准 Bloom filter 演示：对其某个键做「按位清除」式删除会同时清掉其他键共享的比特、从而产生假阴性。把「cuckoo 删除后的假阴性率、被删键的正确移除情况，以及 Bloom 无法安全删除的演示」写到 ./summary_deletion.md。固定设置：b=4、f=12、N、Bloom 的 m/k、随机种子；自变量为是否删除 / 查询集合。

---

[Judge]

Look at `./summary_deletion.md`, check whether conclusion cover the following points

1. cuckoo filter 删除后，保留键的假阴性率为 0（删除不影响其他键）。
2. 被删除的键被正确移除（查询返回不存在）。
3. 标准 Bloom filter 无法安全删除（按位清除会引入假阴性），与 cuckoo 形成对比。


[Judge V2]

查阅 `./summary_deletion.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；b=4、f=12、N=1×10⁵）：

1. 须给删除后保留键假阴性率 0（golden：FNR=0/50000=0.0%；可接受：FNR=0）。（细化原 [Judge] 第 1 点）
2. 须给被删键正确移除（golden：correct-removal=99.942%（29 FP/50000）、fresh FPR=0.0500%；可接受：correct-removal ≥99.9%）。（细化原 [Judge] 第 2 点）
3. 须给标准 Bloom 无法安全删除（按位清零引入假负），与 cuckoo 对比（golden：Bloom 按位删除致假负；可接受：说明 Bloom 按位删除破坏其他键即可）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
