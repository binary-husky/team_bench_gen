[Agents]

读给定材料，做实验，写结论。

考察子样本规模 ψ（max_samples）对异常检测的影响（论文核心洞察）。用 sklearn.datasets.make_blobs 生成约 5000 个正常点（若干簇），再注入约 2% 的均匀分布离群点作为异常（已知标签，固定随机种子）。对 ψ ∈ {16, 32, 64, 128, 256, 512, None(全量)} 分别训练 sklearn.ensemble.IsolationForest（n_estimators=100, random_state=0），用其异常分与真实标签计算检测 AUC（sklearn.metrics.roc_auc_score）。把「检测 AUC 随 ψ 的变化」写到 ./summary_subsample_size.md。固定设置：数据集、n_estimators、random_state；唯一自变量为 ψ。

---

[Judge]

Look at `./summary_subsample_size.md`, check whether conclusion cover the following points

1. 小到中等 ψ（如 ~256）时检测 AUC 高且大致平台（已足够）。
2. 使用全量数据（大 ψ）时 AUC 反而可能下降（淹没/遮蔽效应）。
3. 整体印证论文「小子样本即可、且常更优」的核心洞察。
