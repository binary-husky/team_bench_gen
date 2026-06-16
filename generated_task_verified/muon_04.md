[Agents]

复现 muon 在 cifar-10 上面的实验（./material），配置python环境。

Muon 使用 Jordan (3.4445, -4.7750, 2.0315) 作为 Newton-Schulz 系数基准。训练 SmallCNN (1.26M)。

研究 Muon 的泛化 gap 缓解策略：单变量消融 weight decay / dropout / label smoothing。

至少覆盖：
- 3 baseline（Muon / SGD / AdamW）× 10 epoch
- weight decay 6 值：{0, 1e-4, 5e-4, 1e-3, 2e-3, 5e-3} × 10 epoch
- dropout 4 值：{0.0, 0.1, 0.2, 0.3} × 10 epoch
- label smoothing 3 值：{0.0, 0.05, 0.1} × 10 epoch

挑 top 5 候选跑 30 epoch 复筛。

把结论写到 `./summary_generalization.md`。

---

[Judge (IQ requirement: low-IQ)]

Look at `./summary_generalization.md`, check whether conclusion cover the following points:

1. label smoothing=0.1 是缓解 Muon 泛化 gap 的最有效单一干预（30ep val_acc=0.9258，gap=0.144，−52% vs baseline gap=0.300）
2. weight decay 对 Muon 的 gap 几乎无影响（6 个值下 gap 都在 0.146-0.162 区间内）
3. dropout 仅在短训下缩 gap，30ep 长训反而拖累 val_acc
