[Agents]

读给定材料，做实验，写结论。

考察 FM-index 的「机会式 / 熵有界」体积特性。构造若干等长但可压缩性不同的文本：随机 DNA（几乎不可压缩）、重复/模式化文本（高度可压缩）、普通英文文本。对每段文本构建 BWT，并以 run-length / 简单熵编码（或对小规模直接度量 BWT 的游程数 / 经验熵）度量「索引体积 vs 原文体积」。把「索引/原文体积比 与文本可压缩性的关系」写到 ./summary_index_size.md。固定设置：文本长度、各文本类型、随机种子、度量方式；自变量为文本可压缩性。

---

[Judge]

Look at `./summary_index_size.md`, check whether conclusion cover the following points

1. 对可压缩/重复文本，FM-index 体积小于原文（被压缩）。
2. 对随机文本，索引体积 ≈ 原文体积（不可压缩）。
3. 体现「机会式」、体积随文本熵有界的特性。
