[Agents]

读给定材料，做实验，写结论。

考察 LF-mapping 的可逆性。在同一段文本（约 100KB–500KB，固定种子）上构建 BWT；仅用 BWT（L）、C 数组与 rank，通过反复 LF 映射从 BWT 逐字符反向重建文本，并与原文逐字节比较。把「重建文本与原文的一致性（是否完全相等、首个不匹配位置）」写到 ./summary_lf_mapping.md。固定设置：文本、随机种子、实现；本题为可逆性验证（无超参自变量）。

---

[Judge]

Look at `./summary_lf_mapping.md`, check whether conclusion cover the following points

1. LF-mapping 从 BWT 精确重建出原文（逐字节相等）。
2. 重建是逐字符、自后向前进行的。
3. 确认 BWT 可逆性，正是反向搜索成立的基础。
