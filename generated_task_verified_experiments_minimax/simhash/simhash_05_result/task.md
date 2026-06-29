[Agents]

读给定材料，做实验，写结论。

在同一语料上对比 SimHash（余弦）与 MinHash（Jaccard）。生成若干随机稀疏二值特征向量（可同时视为集合）：对每对同时计算真实余弦相似度（|A∩B|/√(|A||B|)）与真实 Jaccard（|A∩B|/|A∪B|）。用 SimHash（b=256）估计余弦、用 MinHash（可用 datasketch 或自行实现，同样 hash 数）估计 Jaccard，分别计算各自估计误差。把「SimHash 对余弦、MinHash 对 Jaccard 的估计误差对比」以及「二者在同一配对上数值不同」写到 ./summary_vs_minhash.md。固定设置：向量/集合规模、b、hash 数、随机种子；自变量为估计器。

---

[Judge]

Look at `./summary_vs_minhash.md`, check whether conclusion cover the following points

1. SimHash 准确估计余弦相似度（误差低）。
2. MinHash 准确估计 Jaccard（误差低）。
3. 同一配对上两者数值不同（度量不同：余弦 vs Jaccard）。


[Judge V2]

查阅 `./summary_vs_minhash.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；语料 C(500,2)=124750 配对、SimHash b=256 vs MinHash 256 哈希）：

1. 须给 SimHash 准确估余弦(误差低)（golden：SimHash MAE 0.0778（原理 cos(πH/b)）/0.0500（线性 1−2H/b）；可接受：MAE ≤0.1）。（细化原 [Judge] 第 1 点）
2. 须给 MinHash 准确估 Jaccard(误差低)（golden：MinHash Jaccard MAE 低、与 SimHash 同量级；可接受：MinHash Jaccard 误差低）。（细化原 [Judge] 第 2 点）
3. 须给同一配对两者数值不同(度量不同: 余弦 vs Jaccard)（golden：`jac=cos/(2−cos)`、稀疏语料下 `jac≈cos/2`（量级约为余弦一半）；可接受：点明度量不同致数值不同）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
