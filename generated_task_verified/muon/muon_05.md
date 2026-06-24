[Agents]

复现 muon 在 cifar-10 上面的实验（./material），配置python环境。

Muon 使用 Jordan (3.4445, -4.7750, 2.0315) 作为 Newton-Schulz 系数基准。训练 SmallCNN (1.26M)。

研究 Muon 的 update scaling 与 weight decay 交互。

至少对比以下 5 种 update scaling：
1. `paper`：`O *= sqrt(max(1, rows/cols))`，论文默认
2. `none`：不缩放
3. `sqrt_rows_cols`：`O *= sqrt(rows/cols)`，对称版本
4. `rms_match`：把 NS 输出的 RMS 调整到 momentum 的 RMS
5. `spectral_clip`：对 update 做谱范数裁剪（max_norm=1.0）

每种 scaling 配 3 种 weight decay（0、5e-4、2e-3），共 15 组 10 epoch 快筛。

挑 top 5 跑 30 epoch 复筛。

把结论写到 `./summary_update_scaling.md`。

---

[Judge]

Look at `./summary_update_scaling.md`, check whether conclusion cover the following points:

1. paper 默认 scaling（`sqrt(max(1, rows/cols))`）仍是最好的，30ep val_acc=0.9231
2. `rms_match` 退步明显（30ep val_acc=0.9122，−1.09pp，破坏正交化方向性）
3. `spectral_clip` 计算代价 4×（单 epoch 14.8s vs paper 3.6s）但没有精度优势
4. scaling × weight_decay 几乎没有交互（5 种 scaling 在 3 个 wd 下相对排名稳定）
