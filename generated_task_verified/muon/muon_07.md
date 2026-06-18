[Agents]

复现 muon 在 cifar-10 上面的实验（./material），配置python环境。

Muon 使用 Jordan (3.4445, -4.7750, 2.0315) 作为 Newton-Schulz 系数基准。训练 SmallCNN (1.26M)。

诊断 Muon / SGD-Momentum / AdamW 三个优化器在 5 个目标层上的 update 谱特征。

至少覆盖 5 个诊断层：
- `stem` (64×27)
- `block1.conv2` (64×576)
- `block2.conv2` (128×576)
- `block3.conv2` (256×1152)
- `fc1` (128×256)

每个 epoch 末用固定 batch 0 跑 forward+backward，optimizer.step 前 snapshot momentum buffer，step 后用 `(p_after - p_before) / lr` 拿 effective update（不污染训练轨迹）。

每个 optimizer 训练 10 epoch，记录每层每 epoch 的：
- update spectral norm / Frobenius norm
- update effective rank（Roy & Vetterli 2007: `exp(H(p))`, p = σ/Σσ）
- top-10 singular values
- 对照的 gradient / momentum 谱特征

把结论写到 `./summary_spectrum.md`。

---

[Judge (IQ requirement: low-IQ)]

Look at `./summary_spectrum.md`, check whether conclusion cover the following points:

1. Muon 把 update 谱拍平：block1-3 conv 层 top-1/top-10 奇异值比 < 1.05，spec ≈ 1.14
2. Muon 的 update_eff_rank 在 fc1 层（梯度天然低秩 12.10）放大到 125.62（10.4×），SGD/AdamW 都没有这个能力
3. AdamW 的 update spec 是 SGD/Muon 的 50-200×（block3: AdamW=79.7 vs SGD=0.34 vs Muon=1.14），但谱形状与梯度几乎相同
4. Muon 的谱特征在 epoch 1 之后基本不再变化（NS 几何保证），不依赖 lr schedule
