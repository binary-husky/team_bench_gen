[Agents]

读给定材料，做实验，写结论。

考察用 SimHash + 汉明阈值做近重复检测的精度。构造语料：生成若干基础随机向量（d=100），对其中的部分做小幅扰动得到「近重复对」（余弦相似度高，如 ~0.95+），并加入无关向量（余弦相似度低）；已知真实近重复配对（固定随机种子）。用 b=256 的 SimHash 计算所有配对的汉明距离；改变判定阈值 T（汉明距离 ≤ T 视为近重复），记录每个 T 下的 precision 与 recall。把「precision、recall 随汉明阈值 T 的变化」写到 ./summary_near_duplicate.md。固定设置：d、b、语料规模、随机种子；唯一自变量为 T。

---

[Judge]

Look at `./summary_near_duplicate.md`, check whether conclusion cover the following points

1. 随 T 增大，precision 下降、recall 上升。
2. 存在兼顾两者的「甜点」阈值。
3. 近重复对（高余弦）汉明距离小、无关对汉明距离大（分布可分）。
