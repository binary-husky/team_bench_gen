[Agents]

读给定材料，做实验，写结论。

考察用 SimHash + 汉明阈值做近重复检测的精度。构造语料：生成若干基础随机向量（d=100），对其中的部分做小幅扰动得到「近重复对」（余弦相似度高，如 ~0.95+），并加入无关向量（余弦相似度低）；已知真实近重复配对（固定随机种子）。用 b=256 的 SimHash 计算所有配对的汉明距离；改变判定阈值 T（汉明距离 ≤ T 视为近重复），记录每个 T 下的 precision 与 recall。把「precision、recall 随汉明阈值 T 的变化」写到 ./summary_near_duplicate.md。固定设置：d、b、语料规模、随机种子；唯一自变量为 T。

---

[Judge]

Look at `./summary_near_duplicate.md`, check whether conclusion cover the following points

1. 随 T 增大，precision 下降、recall 上升。
2. 存在兼顾两者的「甜点」阈值。
3. 近重复对（高余弦）汉明距离小、无关对汉明距离大（分布可分）。


[Judge V2]

查阅 `./summary_near_duplicate.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；b=256、N_base=300、packed-bit XOR+popcount）：

1. 须给随 T 增大 precision 降、recall 升（golden：T=0..256 逐整数表 pr_table.csv；可接受：T↑ precision↓ recall↑）。（细化原 [Judge] 第 1 点）
2. 须给兼顾两者的甜点阈值（golden：真近重复 max 46、无关 min 79、间隔 [46,79] 零误差阈值带；可接受：存在分离带/甜点）。（细化原 [Judge] 第 2 点）
3. 须给近重复(高余弦)汉明小、无关汉明大、分布可分（golden：`E[Ham]=b·θ/π`、近重复均值 25.6、无关 128.1（≈b/2=128）、与理论 36.8/11.5/128.0 吻合；可接受：近重复<无关且可分）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
