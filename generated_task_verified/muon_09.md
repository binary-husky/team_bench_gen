[Agents]

复现 muon 在 cifar-10 上面的实验（./material），配置python环境。

Muon 使用 Jordan (3.4445, -4.7750, 2.0315) 作为 Newton-Schulz 系数基准，update scaling 使用 `paper`。训练 SmallCNN (1.26M)。

研究模型宽度迁移与 Muon 学习率稳定性：把 SmallCNN 做成可调宽度模型，对比以下 4 个宽度：
1. `0.5x`
2. `1.0x`
3. `1.5x`
4. `2.0x`

每个宽度下对比 Muon、SGD-Momentum、AdamW 三个优化器。学习率网格：
- Muon: `0.01, 0.02, 0.04`
- SGD: `0.05, 0.1, 0.2`
- AdamW: `5e-4, 1e-3, 3e-3`

先训练 10 epoch 完整 lr 网格（4 宽度 × 3 optim × 3 lr = 36 run），再对每个 width/optimizer 选 10ep 最优 lr 跑 30 epoch 复筛（12 run）。

记录每个宽度下的最优 lr、默认 lr 与最优 lr 的差距、best val_acc、训练稳定性。

把结果和结论写到 `./summary_width_transfer.md`。

---

[Judge (IQ requirement: low-IQ)]

Look at `./summary_width_transfer.md`, check whether conclusion cover the following points:

1. 短训 10ep 下 Muon 在 4 个宽度（0.5x/1.0x/1.5x/2.0x）都是最强 optimizer
2. Muon 默认 lr=0.02 跨宽度最稳定（1.0x/1.5x/2.0x 正好最优，0.5x 仅 −0.13pp）
3. 30ep 长训结果与短训不同：SGD 在 0.5x/1.0x 反超 Muon（0.5x: SGD 90.90% vs Muon 90.19%），Muon 在 1.5x/2.0x 领先（2.0x: Muon 93.22% vs SGD 92.68%）
4. 48 个 run（36 个 10ep + 12 个 30ep）全部稳定完成，无 NaN 或明显 loss spike
