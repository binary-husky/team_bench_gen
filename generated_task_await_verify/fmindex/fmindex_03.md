[Agents]

读给定材料，做实验，写结论。

考察 LF-mapping 的可逆性。在同一段文本（约 100KB–500KB，固定种子）上构建 BWT；仅用 BWT（L）、C 数组与 rank，通过反复 LF 映射从 BWT 逐字符反向重建文本，并与原文逐字节比较。把「重建文本与原文的一致性（是否完全相等、首个不匹配位置）」写到 ./summary_lf_mapping.md。固定设置：文本、随机种子、实现；本题为可逆性验证（无超参自变量）。

---

[Judge]

Look at `./summary_lf_mapping.md`, check whether conclusion cover the following points

1. LF-mapping 从 BWT 精确重建出原文（逐字节相等）。
2. 重建是逐字符、自后向前进行的。
3. 确认 BWT 可逆性，正是反向搜索成立的基础。


[Judge V2]

查阅 `./summary_lf_mapping.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；N=262144 字节、seed=20240626、纯 Python）：

1. 须给 LF-mapping 从 BWT 精确重建原文、逐字节相等（golden：256KB 文本完全相等、首个不匹配位置=无；可接受：完全相等、无不匹配）。（细化原 [Judge] 第 1 点）
2. 须给重建逐字符、自后向前进行（从第 0 行反复 `LF` 收集 `L[i]` 得正文逆序再反转；golden：重建耗时 0.13s < 构造 0.51s；可接受：说明逐字符后向流程）。（细化原 [Judge] 第 2 点）
3. 须确认 BWT 可逆性是反向搜索基础——`LF` 为双射（以 `L[i]` 结尾的行一一对应以 `L[i]` 开头的行，沿哨兵行反复 LF 逆序遍历原文不丢不重排）；可接受：点明 LF 双射 + 反向搜索基础。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
