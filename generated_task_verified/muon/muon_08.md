[Agents]

复现 muon 在 cifar-10 上面的实验（./material），配置python环境。

Muon 使用 Jordan (3.4445, -4.7750, 2.0315) 作为 Newton-Schulz 系数基准。训练 SmallCNN (1.26M)。

研究 Muon 的鲁棒性：3 类数据集变体 × 3 个优化器。

3 类数据集变体：
1. **小数据**：stratified 随机子集 N ∈ {5000, 10000, 25000, 50000}
2. **标签噪声**：full 50k，symmetric noise p ∈ {0%, 10%, 20%, 40%}
3. **long-tail**：class-imbalanced，max/min ratio ∈ {10, 50}，head class 5000 样本

3 个优化器：
- **Muon**（lr=0.02, momentum=0.95, Nesterov=true, paper scaling）
- **SGD-Momentum**（lr=0.1, momentum=0.9, Nesterov=true, wd=5e-4）
- **AdamW**（lr=3e-3, betas=(0.9, 0.999), wd=5e-4）

测试集永远使用 clean 10k test。

总共 30 runs × 10 epoch。如果现象明显再做 30 epoch 复筛。

把结论写到 `./summary_robustness.md`。

---

[Judge]

Look at `./summary_robustness.md`, check whether conclusion cover the following points:

1. Muon 在所有 30/30 个 robustness variants（4 小数据 + 4 噪声 + 2 long-tail）上都是 #1
2. 数据越少 / 噪声越大 / ratio 越大，Muon 优势越显著：N=5k 时 +10.2pp vs SGD，40% 噪声时 +5.4pp vs SGD，ratio=50 tail_acc +23.6pp vs SGD
3. Muon 不容易过拟合噪声标签（40% noise 下 Muon 仍有 0.848 val_acc，SGD/AdamW 跌到 0.79）
