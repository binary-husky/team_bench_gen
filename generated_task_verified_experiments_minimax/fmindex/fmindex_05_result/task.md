[Agents]

读给定材料，做实验，写结论。

将 FM-index 计数/定位 与朴素子串搜索的查询速度对比。在同一段文本（约 100KB–200KB，固定种子）上构建 FM-index；对一组随机模式（若干条），分别测量：(a) FM-index backward-search 计数时间；(b) FM-index 定位时间（locate，经 LF 步行还原位置）；(c) 朴素 O(n·m) 子串搜索时间。把「计数 / 定位 / 朴素 三者单次查询时间与多查询总时间」写到 ./summary_speed_vs_naive.md。固定设置：文本、模式集合、随机种子、实现；自变量为查询方式。

---

[Judge]

Look at `./summary_speed_vs_naive.md`, check whether conclusion cover the following points

1. FM-index 计数远快于朴素子串搜索（建好索引后）。
2. 多查询时优势放大（建索引成本被摊薄）。
3. 定位比计数慢（需还原位置），但仍具竞争力。


[Judge V2]

查阅 `./summary_speed_vs_naive.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；150KB DNA 文本、40 模式、seed=12345）：

1. 须给 FM 计数远快于朴素（golden：count ~3–6µs vs naive ~8700–12000µs、比值 ~3e-4；可接受：count/naive ≤1e-3）。（细化原 [Judge] 第 1 点）
2. 须给多查询优势放大（建索引成本摊薄）（golden：建索引 64.3ms、每查询 ~3–6µs；可接受：说明建索引一次性 + 多查询摊薄）。（细化原 [Judge] 第 2 点）
3. 须给定位比计数慢但仍具竞争力（golden：locate ~5–25µs > count ~3–6µs、仍远快于朴素（比值 ~5e-4）；可接受：locate>count 且 locate/naive ≤1e-2）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
