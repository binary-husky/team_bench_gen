[Agents]

读给定材料，做实验，写结论。

考察 FM-index 反向搜索 count(pattern) 的正确性。用一段文本（约 100KB–500KB，如随机 DNA 串或英文文本，固定随机种子；构建 BWT 时用后缀数组以保证构造速度）。从零实现 FM-index：构建 BWT、C 数组、对 L 的 rank 支持（可用计数/小波树），实现 backward-search 计数。对若干随机模式（不同长度、含出现/不出现/边界情形），分别用反向搜索与暴力子串计数（brute-force）计算出现次数，比较是否一致。把「反向搜索计数 vs 暴力计数 的一致性（匹配率/差异）」写到 ./summary_count_correctness.md。固定设置：文本、模式集合、随机种子、实现；本题为正确性验证（无超参自变量）。

---

[Judge]

Look at `./summary_count_correctness.md`, check whether conclusion cover the following points

1. 对所有测试模式，反向搜索计数与暴力子串计数完全一致。
2. 覆盖各类字符与边界情形（出现 / 不出现 / 重叠出现）。
3. 确认 FM-index 计数操作正确。
