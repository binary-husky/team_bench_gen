[Agents]

读给定材料，做实验，写结论。

将 FM-index 计数/定位 与朴素子串搜索的查询速度对比。在同一段文本（约 100KB–200KB，固定种子）上构建 FM-index；对一组随机模式（若干条），分别测量：(a) FM-index backward-search 计数时间；(b) FM-index 定位时间（locate，经 LF 步行还原位置）；(c) 朴素 O(n·m) 子串搜索时间。把「计数 / 定位 / 朴素 三者单次查询时间与多查询总时间」写到 ./summary_speed_vs_naive.md。固定设置：文本、模式集合、随机种子、实现；自变量为查询方式。

---

[Judge]

Look at `./summary_speed_vs_naive.md`, check whether conclusion cover the following points

1. FM-index 计数远快于朴素子串搜索（建好索引后）。
2. 多查询时优势放大（建索引成本被摊薄）。
3. 定位比计数慢（需还原位置），但仍具竞争力。
