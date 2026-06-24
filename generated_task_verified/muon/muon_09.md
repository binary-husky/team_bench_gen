[Agents]

复现 muon 在 cifar-10 上面的实验（./material），配置python环境。

Muon 使用 Jordan (3.4445, -4.7750, 2.0315) 作为 Newton-Schulz 系数基准，update scaling 使用 `paper`。训练 SmallCNN (1.26M)。

研究模型宽度迁移与 Muon 学习率稳定性：把 SmallCNN 做成可调宽度模型，对比以下 4 个宽度：
1. `0.5x`（约 0.32M 参数）
2. `1.0x`（约 1.26M 参数）
3. `1.5x`（约 2.84M 参数）
4. `2.0x`（约 5.04M 参数）

每个宽度下对比 Muon、SGD-Momentum、AdamW 三个优化器。学习率网格：
- Muon: `0.01, 0.02, 0.04`（default 0.02）
- SGD: `0.05, 0.1, 0.2`（default 0.1）
- AdamW: `5e-4, 1e-3, 3e-3`（default 3e-3）

10ep 阶段：4 widths × 3 optims × 3 lr = **36 runs** 完整 lr 网格快筛。
30ep 阶段：3 关键宽度（0.5x / 1.0x / 2.0x）× 3 optims × default lr = **9 runs** 复筛。

共 **45 runs**。

记录每个宽度下的最优 lr、default lr 与最优 lr 的差距、best val_acc、训练稳定性。

把结果和结论写到 `./summary_width_transfer.md`。

---

[Judge]

Look at `./summary_width_transfer.md`, check whether conclusion cover the following points:

1. 10ep 训练下 Muon 在 4/4 宽度（0.5x=0.881, 1.0x=0.903, 1.5x=0.915, 2.0x=0.921）都是 #1 优化器
2. Muon 在 3 个 lr（0.01/0.02/0.04）上的 spread 跨 4 个宽度都 < 0.4pp（default lr 几乎不需要重调）
3. SGD 在 1.0x 时 default lr=0.1 偏小（被 lr=0.2 击败 -0.48pp）；AdamW 在 1.5x/2.0x 时 default lr=3e-3 偏大（被 lr=5e-4 击败），两个都需要 per-width 调 lr
4. 30ep 排名随宽度变化：0.5x 时 SGD 反超 Muon +0.56pp（0.9076 vs 0.9020），1.0x 持平（0.9201=0.9201），2.0x Muon 重新领先 +0.53pp（0.9316 vs 0.9263）
5. Muon 早收敛：10ep→30ep 提升只有 1-2pp，SGD/AdamW 同期提升 3.4-4.5pp
6. 全部 45 个 run 无 NaN、无 loss spike
