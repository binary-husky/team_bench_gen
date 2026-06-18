[Agents]

复现 muon 在 cifar-10 上面的实验（./material），配置python环境。

Muon 使用 Jordan (3.4445, -4.7750, 2.0315) 作为 Newton-Schulz 系数基准。训练 SmallCNN (1.26M)。

研究 Muon 的 momentum / Nesterov / 辅助 AdamW 学习率三个超参。

至少覆盖：
1. **momentum**：6 值 {0.0, 0.6, 0.8, 0.9, 0.95, 0.98}（0.95 是 paper 默认）
2. **Nesterov**：{true, false}（默认 true）
3. **aux AdamW lr ratio**（= aux_lr / muon_lr）：5 值 {0.01, 0.025, 0.05, 0.1, 0.2}（0.05 是 paper 默认）

共 12 组 10 epoch 快筛。挑 5 组 30 epoch 复筛。

把结论写到 `./summary_momentum_auxadam.md`。

---

[Judge (IQ requirement: low-IQ)]

Look at `./summary_momentum_auxadam.md`, check whether conclusion cover the following points:

1. aux_lr_ratio 从 0.05 提到 0.1 是这一组唯一显著的提升（30ep val_acc=0.9244，+0.52pp vs paper default）
2. Nesterov 关掉几乎无代价也无收益（30ep 仅 −0.05pp），建议保留
3. momentum=0.0 在 10ep/30ep 都是末位（30ep val_acc=0.9100），不保留任何早期优势
