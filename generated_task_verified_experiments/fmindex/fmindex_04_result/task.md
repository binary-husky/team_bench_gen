[Agents]

读给定材料，做实验，写结论。

考察 FM-index 的「机会式 / 熵有界」体积特性。构造若干等长但可压缩性不同的文本：随机 DNA（几乎不可压缩）、重复/模式化文本（高度可压缩）、普通英文文本。对每段文本构建 BWT，并以 run-length / 简单熵编码（或对小规模直接度量 BWT 的游程数 / 经验熵）度量「索引体积 vs 原文体积」。把「索引/原文体积比 与文本可压缩性的关系」写到 ./summary_index_size.md。固定设置：文本长度、各文本类型、随机种子、度量方式；自变量为文本可压缩性。

---

[Judge]

Look at `./summary_index_size.md`, check whether conclusion cover the following points

1. 对可压缩/重复文本，FM-index 体积小于原文（被压缩）。
2. 对随机文本，索引体积 ≈ 原文体积（不可压缩）。
3. 体现「机会式」、体积随文本熵有界的特性。


[Judge V2]

查阅 `./summary_index_size.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；N=65536、4 类文本、seed=12345）：

1. 须给可压缩/重复文本索引体积 < 原文（golden：重复 DNA 索引/原文 ~0.5%、随机 DNA ≈1 或略 >1、英文居中；可接受：重复文本比值 <0.1、随机 ≈1）。（细化原 [Judge] 第 1 点）
2. 须给随机文本索引体积 ≈ 原文（不可压缩，H_k≈logσ）（golden：随机 DNA 比值 ≈1 或略 >1（编码开销）；可接受：∈[0.9,1.2]）。（细化原 [Judge] 第 2 点）
3. 须体现机会式、体积随熵有界（golden：`|BW_RLX|≤5·|T|·H_k+g_k·log|T|`、BWT 游程数 r 为中介；可接受：点明熵有界 + r 中介）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
