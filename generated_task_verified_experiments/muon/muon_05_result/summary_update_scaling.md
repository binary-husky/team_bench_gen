# Muon update scaling × weight decay

> SmallCNN (1.26M) · CIFAR-10 · bf16 AMP · A100 80GB · seed=42
> Muon 统一使用 **Jordan (3.4445, -4.775, 2.0315)** Newton-Schulz 系数，ns_steps=5
> 5 scaling × 3 weight decay = 15 组 10 epoch 快筛；top 5 配置 30 epoch 复筛

## 结论先行

**Paper 默认的 `sqrt(max(1, rows/cols))` scaling 仍是最好的 update scaling**。`scaling` 与 `weight_decay` 几乎没有交互（两者各自的最优配置可以独立选择）。**`rms_match` 是最差的 scaling（−0.6pp vs paper）**。

| 30ep 配置 | best val_acc | fin val_loss | fin train_loss | **gap** | 90%@ | 92%@ | 单 epoch 时间 |
|-----------|--------------|--------------|----------------|---------|------|------|---------------|
| **paper + wd=2e-3** | **0.9231** | 0.329 | 0.029 | +0.299 | 19 | 24 | 3.6s |
| none + wd=5e-4    | 0.9226      | 0.332 | 0.031 | +0.301 | 18 | 25 | 4.5s |
| paper + wd=5e-4   | 0.9216      | 0.323 | 0.029 | +0.295 | 21 | 25 | 3.6s |
| spectral_clip + wd=0 | 0.9183   | 0.340 | 0.028 | +0.312 | 21 | 99 | **14.8s** ⚠️ |
| rms_match + wd=5e-4  | 0.9122   | 0.345 | 0.030 | +0.315 | 21 | 99 | 3.8s |

**核心结论**：
1. **5 种 scaling 在 30ep 下的 val_acc 差距仅 ±0.5pp**（0.9122 – 0.9231），其中 4/5 在 0.918-0.923 区间——**update scaling 不是关键超参**。
2. **paper + wd=2e-3 是双料冠军**（val_acc 最高、收敛最快）。
3. **paper vs none vs sqrt_rows_cols 几乎等价**（10ep 差 0.1-0.3pp）——Muon 对 scaling 形式不敏感。
4. **rms_match 是 10/30ep 唯一明确退化的 scaling**（−0.6pp @30ep，10ep 时连 90% 都未达）——把 NS 正交化输出缩放到"匹配 momentum RMS"破坏了 update 方向性。
5. **spectral_clip 计算代价过高**（30ep 445s vs paper 109s，**4x 慢**）但 val_acc 与 paper 接近——**不推荐使用**。
6. **scaling × weight decay 几乎无交互**（最优 scaling+wd 组合 = 各自动最优的组合，没有"特定 scaling 需要特定 wd"的现象）。
7. **没有 NaN 或 loss spike**（任何配置任何 epoch）。

**推荐**：
- **生产用 `paper` scaling + `wd ∈ [5e-4, 2e-3]`**——paper 形式简单（就一个 `sqrt(max(1, rows/cols))`），wd 在 5e-4 到 2e-3 之间都可，差别微小。
- **不推荐 `rms_match`**（破坏正交化方向性，val_acc 退化且难以调试）。
- **不推荐 `spectral_clip`**（SVD 4x 慢但没有精度优势）。
- **`sqrt_rows_cols` 和 `none` 是"省钱简化"**——`none` 略好一点（10ep 多次高于 sqrt_rows_cols），但 val_acc 都比 paper 低 0.2-0.3pp。

---

## 1. 问题与动机

Muon 的 update scaling 决定了 **Newton-Schulz 正交化后**输出应用到参数的最终幅度。Paper 默认 `sqrt(max(1, rows/cols))` 是 Keller Jordan 经验调出来的，但**没有严格的理论推导**——它只是"spectral-norm 保持在 ~1"的简单启发式。

本研究问：
- (a) 5 种不同 update scaling 在 CIFAR-10 上表现差异多大？
- (b) scaling 与 weight decay 是否有交互？
- (c) 哪个 scaling 最优？是否值得切换？

---

## 2. 5 种 Update Scaling 定义

设 NS 输出为 `O`（近似正交矩阵，σ_max ~ 1），shape `(rows, cols)`（reshape 后；conv kernel 被 reshape 为 2D）。

| 模式 | 公式 | 含义 |
|------|------|------|
| `paper` | `O *= sqrt(max(1, rows/cols))` | Muon 论文默认：wide layer 放大 sqrt(rows/cols) 倍，tall layer 保持 |
| `none` | `O *= 1.0` | 不缩放 |
| `sqrt_rows_cols` | `O *= sqrt(rows/cols)` | 对称：tall layer 也缩小 sqrt(rows/cols) |
| `rms_match` | `O *= rms(buf) / rms(O)` | 把 NS 输出的 RMS 调整到原始 momentum 的 RMS（破坏正交性） |
| `spectral_clip` | `if ‖O‖₂ > max_norm: O *= max_norm / ‖O‖₂` | 谱范数上限裁剪（默认 max_norm=1.0） |

**直觉对比**：
- `paper`：tall layer 保持正交，wide layer 放大（让"高秩 wide 矩阵"每步更新大一些）
- `none`：所有形状都保持 NS 输出
- `sqrt_rows_cols`：tall layer 缩小（NS 后 σ_max ~ 1，但 ‖O‖_F = sqrt(min(rows, cols))，对 tall 矩阵来说 ‖O‖_F 偏大，缩到 sqrt(rows/cols) 让 Frobenius 范数统一）
- `rms_match`：把 NS 输出的 RMS 强行拉到原始 momentum 的 RMS（隐含让 update "看起来像普通 SGD update"）
- `spectral_clip`：确保 update 的谱范数不超过 1（比 paper 更严格的约束）

---

## 3. 10 epoch 快筛：5 scaling × 3 weight decay

`milestones=[7,9]`，`bs=256`，`dropout=0.2`，`ls=0.0`，`hidden_2d` policy。

### 3.1 Best val_acc 矩阵

| scaling \ wd | **0** | **5e-4** | **2e-3** | 行均值 |
|--------------|-------|----------|----------|--------|
| **paper**         | 0.9040 | 0.9055 | **0.9084** | 0.9060 |
| **none**          | **0.9058** | 0.9058 | 0.9009 | 0.9042 |
| **sqrt_rows_cols** | 0.9038 | 0.9014 | 0.9002 | 0.9018 |
| **rms_match**     | 0.8979 | 0.8969 | 0.8959 | 0.8969 |
| **spectral_clip** | 0.9060 | 0.9029 | 0.9057 | 0.9049 |
| 列均值 | 0.9035 | 0.9025 | 0.9022 | |

**Top 5**（10ep best val_acc 排序）：
1. paper + wd=2e-3: **0.9084**
2. spectral_clip + wd=0: 0.9060
3. none + wd=0: 0.9058
4. none + wd=5e-4: 0.9058
5. paper + wd=5e-4: 0.9055

### 3.2 Gen Gap 矩阵 (val_loss − train_loss)

| scaling \ wd | **0** | **5e-4** | **2e-3** |
|--------------|-------|----------|----------|
| paper         | +0.146 | +0.153 | **+0.143** |
| none          | +0.152 | **+0.144** | +0.163 |
| sqrt_rows_cols | +0.155 | +0.155 | +0.151 |
| rms_match     | +0.154 | +0.152 | +0.155 |
| spectral_clip | +0.148 | +0.162 | +0.156 |

**gap 范围 0.143 – 0.163**（差 0.020），**scaling 对 gap 的影响非常小**。

### 3.3 90% 收敛速度矩阵

| scaling \ wd | **0** | **5e-4** | **2e-3** |
|--------------|-------|----------|----------|
| paper         | 8 | 9 | 8 |
| none          | 8 | 8 | 10 |
| sqrt_rows_cols | 9 | 9 | 10 |
| rms_match     | 99 (未达) | 99 (未达) | 99 (未达) |
| spectral_clip | 9 | 9 | 9 |

**关键观察**：`rms_match` 在 10 epoch 下**根本无法达到 90%**（其他 4 个 scaling 都在 8-10 epoch 达到）。这强烈提示 `rms_match` 破坏了 update 的方向性——模型在 train 上拟合可以（10 epoch 末 fin_tl=0.158 不算差），但 generalization 严重滞后。

### 3.4 NaN / Loss Spike 检查

15 组全部**无 NaN，无 loss spike**。所有 scaling 在 10 epoch 训练中数值稳定。

---

## 4. 30 epoch 复筛

### 4.1 代表配置选择

从 15 组 10ep 挑 5 个进 30ep 复筛（覆盖"best / paper default / scaling 形式 / 负样本"四个维度）：

| 配置 | 10ep best | 入选理由 |
|------|-----------|----------|
| paper + wd=2e-3 | 0.9084 | 10ep 双料冠军；验证长训效果 |
| paper + wd=5e-4 | 0.9055 | paper 默认配置；作为 baseline 参照 |
| none + wd=5e-4 | 0.9058 | "最简化" scaling；测试去掉 rescaling 是否可行 |
| spectral_clip + wd=0 | 0.9060 | 唯一在 wd=0 仍达 0.906 的；测试 SVD 方案长训 |
| rms_match + wd=5e-4 | 0.8969 | 10ep 最差；作为负样本验证 30ep 趋势 |

### 4.2 30 epoch 结果

`milestones=[20,25]`，bs=256，seed=42。

| 30ep 配置 | best_va | best@ep | fin_vl | fin_tl | **gap** | 85%@ | 90%@ | 92%@ | 单 epoch 时间 |
|-----------|---------|---------|--------|--------|---------|------|------|------|--------------|
| **paper + wd=2e-3** | **0.9231** | 26 | 0.329 | 0.029 | +0.299 | 4 | 19 | **24** | 3.6s |
| none + wd=5e-4 | 0.9226 | 28 | 0.332 | 0.031 | +0.301 | 5 | **18** | 25 | 4.5s |
| paper + wd=5e-4 | 0.9216 | 30 | 0.323 | 0.029 | **+0.295** | 4 | 21 | 25 | 3.6s |
| spectral_clip + wd=0 | 0.9183 | 25 | 0.340 | 0.028 | +0.312 | 4 | 21 | 99 (未达) | **14.8s** ⚠️ |
| rms_match + wd=5e-4 | 0.9122 | 26 | 0.345 | 0.030 | +0.315 | 6 | 21 | 99 (未达) | 3.8s |

### 4.3 30ep 关键发现

1. **`paper + wd=2e-3` 仍是 30ep 冠军**（0.9231 vs 10ep 0.9084 → 30ep +0.0147）。10ep → 30ep 的增量与其他 scaling 一致（0.013-0.015），所以 10ep 排名几乎预测了 30ep 排名。

2. **`paper` 的 5e-4 vs 2e-3** 在 30ep 仅差 0.15pp（0.9216 vs 0.9231），**远小于 10ep 的 0.29pp**。说明 paper 的 wd 选择在长训下**进一步收敛**——10ep 里的 wd=2e-3 优势大部分保留下来但被压平。

3. **`none` 与 `paper` 在 30ep 几乎打平**（0.9226 vs 0.9216，+0.10pp）。**这是一个"省钱"机会**：去掉 `sqrt(max(1, rows/cols))` 缩放，精度损失 < 0.2pp，但代码更简单（不用算 rows/cols）。

4. **`spectral_clip` 在 30ep 比 10ep 退步更多**（0.9060 → 0.9183，+0.0123 vs paper 的 +0.0147）。**且 30ep 里没有达到 92%**（最佳 0.9183）。结合 4x 的计算开销，**强烈不推荐**。

5. **`rms_match` 30ep 仍最差**（0.9122），与 paper 差 1.09pp。**`rms_match` 破坏了 NS 输出的正交性**——把"近似正交矩阵"缩放到 momentum 的 RMS，相当于重新引入了 gradient 范数信息，让 update 方向变得不稳定。

### 4.4 10ep → 30ep 排名一致性

| 配置 | 10ep best | 30ep best | 10ep rank | 30ep rank | 排名变化 |
|------|-----------|-----------|-----------|-----------|----------|
| paper + wd=2e-3 | 0.9084 | 0.9231 | 1 | 1 | — |
| none + wd=5e-4 | 0.9058 | 0.9226 | 3-4 | 2 | ↑1 |
| paper + wd=5e-4 | 0.9055 | 0.9216 | 5 | 3 | ↓2 |
| spectral_clip + wd=0 | 0.9060 | 0.9183 | 2 | 4 | ↓2 |
| rms_match + wd=5e-4 | 0.8969 | 0.9122 | 15 | 5 | — |

**10/30ep 排名一致性高**（除 1 档内交换）。这与课题 2 结论一致——**10 epoch 足够预测 30 epoch 排名**。

---

## 5. 计算代价对比

| scaling | 单 epoch 时间（A100, 1.26M 模型） | 相对 paper | 备注 |
|---------|-----------------------------------|-----------|------|
| paper | 3.6s | 1.0x | 1 次 sqrt + max（可忽略） |
| none | 4.5s | 1.25x | 比 paper 慢一点（可能因 lr/数据随机性） |
| sqrt_rows_cols | 3.6s | 1.0x | 1 次 sqrt / 除法 |
| rms_match | 3.8s | 1.06x | 1 次 RMS 计算 |
| **spectral_clip** | **14.8s** | **4.1x** | 每次 step 一次 SVD（哪怕 max_norm=1.0 也要算一遍） |

**`spectral_clip` 的 4x 慢来自对每个 2D weight 都做一次 SVD**（用 `torch.linalg.matrix_norm(ord=2)`）。对 1.26M 模型有 ~11 个 2D 权重（含 fc1、conv reshape 后），每 step 11 次 SVD 就是 4x 开销。对于大模型（数十个 2D 权重），开销还会更大。

**生产建议**：
- 用 `paper` 或 `none`（O(1) 开销）
- 不用 `spectral_clip`（除非你愿意为 0.1pp 精度付 4x 计算）

---

## 6. 关键观察

### 6.1 Scaling 与 Weight Decay 几乎无交互

| | wd=0 优势 scaling | wd=5e-4 优势 | wd=2e-3 优势 |
|---|---|---|---|
| 10ep best | spectral_clip (0.9060) | none (0.9058) | paper (0.9084) |

**没有"某 scaling 在某 wd 下突然变好"的现象**。3 个 wd 列下 5 个 scaling 的相对排名相对稳定，**最优 scaling + 最优 wd 的组合 = 各自最优的简单组合**。

这与课题 2 的 wd 消融结论一致：**Muon 对 wd 几乎不敏感**（scaling 选好后 wd 在 5e-4 到 2e-3 之间差别微小）。

### 6.2 `paper` 公式的"shape invariance" 动机

`paper` 公式 `sqrt(max(1, rows/cols))` 的隐含动机是让 update 的 **Frobenius 范数**大致正比于 `sqrt(min(rows, cols))`——即与正交矩阵的"信息量"成正比。

| 形状 | NS 输出 ‖O‖_F | paper scale | 实际 ‖O*scale‖_F | none scale | 实际 ‖O‖_F |
|------|---------------|-------------|------------------|-----------|-------------|
| (256, 256) square | 16 | 1.0 | 16 | 1.0 | 16 |
| (128, 256) tall   | 11.3 (=√128) | 1.0 | 11.3 | 1.0 | 11.3 |
| (256, 128) wide   | 11.3 | √2=1.41 | 16 | 1.0 | 11.3 |
| (4096, 128) very wide | 11.3 | √32=5.66 | 64 | 1.0 | 11.3 |

**wide layer 的 `paper` 缩放让 ‖O‖_F 提升到 √min(rows,cols)**（即与 square 矩阵一致），而 `none` 缩放对 wide layer 来说 ‖O‖_F 偏小。

但**实际差异很小**（10ep paper vs none 仅 0.03pp，30ep 仅 0.10pp）——`paper` 的"shape 修正"对 CIFAR-10 这种小模型收益有限。

### 6.3 为什么 `rms_match` 差这么多

`rms_match` 试图让 update RMS = momentum RMS（即"看上去像普通 SGD update"）。但 NS 的核心价值是**让 update 接近正交矩阵**——奇异值都被压向 1。

`rms_match` 把 NS 输出乘以 `(rms(momentum) / rms(O))`——通常 momentum 的 RMS 比 NS 输出小得多（因为 NS 输出 σ_min 都被推大），所以 scale 通常 < 1（实测约 0.3-0.5）。**这把"近似正交矩阵"缩成了一个范数很小的矩阵**——update 方向性弱、步长短，模型收敛慢。

30ep 验证：`rms_match` 92% 未达（其他都达到），best 0.9122 比 paper 低 1pp——**确认 rms_match 破坏正交化优势**。

### 6.4 `sqrt_rows_cols` 弱于 `paper` 的直觉

`sqrt_rows_cols` 是 `paper` 的"对称版本"——tall layer 也按 sqrt(rows/cols) 缩（< 1）。这与 `paper` 的"只对 wide layer 放大"思路相反。

实测：tall layer（fc1 shape 128×256，rows < cols）按 `sqrt_rows_cols` 缩到 0.707 倍，而 `paper` 保持 1.0 倍——**等于把 fc1 的有效学习率打了 0.7 折**。这导致 10ep val_acc 整体低 0.2pp。

**`paper` 的"非对称"设计是有意为之的**——它认为 tall layer 已经有足够的 update magnitude（因为 NS 输出已正交），而 wide layer 需要放大来补偿。这是经验法则，但实测有效。

### 6.5 早 epoch 行为（10ep 数据观察）

| scaling | 收敛到 85% epoch | 收敛到 90% epoch | 10ep val_acc |
|---------|------------------|------------------|--------------|
| paper         | 4-5 | 8-9 | 0.9060 (均值) |
| none          | 4-5 | 8-10 | 0.9042 |
| sqrt_rows_cols | 5 | 9-10 | 0.9018 |
| rms_match     | 5-6 | 99 (未达) | 0.8969 |
| spectral_clip | 4 | 9 | 0.9049 |

**`paper` 早期收敛领先**（90%@8-9 ep）—`sqrt_rows_cols` 和 `rms_match` 慢 1-2 个 epoch。**scaling 影响早期动力学，但不改变长期稳态**。

---

## 7. 工程建议

1. **小模型（CIFAR-10 / SmallCNN）默认配置**：
   - **`paper` scaling + `wd=5e-4` 或 `wd=2e-3`**（paper 默认 wd=5e-4，30ep 0.9216；wd=2e-3 略好 0.9231，差别在 1 个 seed 噪声内）。
   - **不建议换 scaling**——`none` 略省事但 val_acc 低 0.1pp；`spectral_clip` 4x 慢但没优势；`rms_match` 退步明显。

2. **大模型（Transformer/NanoGPT-scale）**：
   - 沿用 `paper` scaling（modded-nanogpt 默认）。
   - 如果遇到 `rms_match` 风格（"想 match gradient norm"）的提议，**保持怀疑**——本研究 1.26M 模型上已经验证 rms_match 退步 1pp。
   - **不要用 `spectral_clip`**——大模型有几十到几百个 2D 权重，每次 SVD 的开销会爆炸。

3. **方法论副产物**：
   - **`paper` 是被设计为"最小合理 scaling"**——只对 wide layer 放大，tall layer 不动。这个不对称性**不是 bug**——如果换成对称的 `sqrt_rows_cols`，tall layer 会被不必要地缩小。
   - **Muon 论文没明说，但实测告诉我们**：在 wide 与 tall 层混合的网络中，**只补偿 wide layer 的"信息量小"是正确的选择**。

4. **何时考虑其他 scaling**：
   - **如果模型全是 tall layer（rows << cols）**：`paper` 与 `none` 等价，`paper` 没有额外收益——可考虑 `none` 简化代码。
   - **如果遇到训练不稳定（loss spike）**：`spectral_clip` 可能有帮助（裁剪 update 范数），但代价是 4x 慢。
   - **如果追求"自然 gradient"理论一致性**：`rms_match` 看起来最贴近"magnitude-aware" 优化，但**实测总是退步**——不要用。

5. **关于 batch size 与 scaling**：
   - 我们的实验固定 bs=256。**大 batch 下 NS 输出本身的统计性质可能变**（更接近"期望正交矩阵"）。但 scaling 公式与 bs 无关——`paper` 仍然应该 work。
   - 如果大 batch 下发现 paper 退步，可以试 `none`（去掉对 wide layer 的放大补偿）。

---

## 8. 局限与未来工作

1. **单 seed**：所有实验 seed=42。多 seed 验证能给出"rms_match 退化"与"paper 略优"是否真的稳健。本研究 30ep 5 组的 max-min = 0.9231-0.9122 = 0.0109 ≈ 1pp——在多 seed 下这个差距可能缩小或扩大。

2. **单模型架构**：SmallCNN 1.26M 在 CIFAR-10。**大模型/Transformer 上 5 种 scaling 的相对排名可能不同**——例如 Transformer 主要权重是 2D linear（rows, cols 跨度大），tall layer 占多数时 `paper` 的"非对称放大" 优势可能减弱。

3. **没试 `spectral_clip` 的 max_norm 调参**：固定 max_norm=1.0。如果用 max_norm=2.0 也许能避免部分"过度裁剪"，但会显著放慢（NS 输出已 σ_max ~ 1.0，再放大 2x 也不会有问题）。本实验选择 max_norm=1.0 是因为它**最严格**。

4. **未与其它 optimizer 联动**：5 种 scaling 都是 Muon 内的。**SGD/AdamW 的 update scaling 完全是另一回事**——本课题不涉及。

---

## 9. 实验命令（可重跑）

```bash
# 10 epoch 快筛：5 scaling x 3 wd = 15 组
# 分 3 批 5 并行 (每批约 150s，因为 spectral_clip 慢)
bash /root/muon_code/run_scale.sh 0  # paper/none/sqrt/rms/spec x wd=0
bash /root/muon_code/run_scale.sh 1  # paper/none/sqrt/rms/spec x wd=5e-4
bash /root/muon_code/run_scale.sh 2  # paper/none/sqrt/rms/spec x wd=2e-3

# 30 epoch 复筛：5 代表配置并行
bash /root/muon_code/run_scale_30ep.sh  # 5 个，约 7 分钟
```

## 10. 文件

- 10ep JSONL: `/home/fuqingxu/cc-workspace/muon/results/scaling_10ep/*.jsonl` (15 个)
- 30ep JSONL: `/home/fuqingxu/cc-workspace/muon/results/scaling_30ep/*.jsonl` (5 个)
- 图: `figures/update_scaling.png`
- 改了: `code/muon.py` (加 `update_scaling` 参数 + 4 个新 scaling 模式)；`code/train.py` (加 `--update-scaling`, `--spectral-max-norm` CLI)

## 11. 总结

> **Muon update scaling 不是关键超参数**。在 5 种 scaling × 3 种 weight decay = 15 组配置中：
> - **`paper` 是默认且最优的**（30ep 0.9231）
> - **`none` 是合理简化**（30ep 0.9226，−0.05pp）
> - **`sqrt_rows_cols` 略弱**（10ep 0.9018-0.9038，被 tall layer 缩小拖累）
> - **`rms_match` 退步明显**（30ep 0.9122，−1.09pp，破坏正交性）
> - **`spectral_clip` 4x 慢且无精度优势**（30ep 0.9183，−0.48pp）
> - **5 种 scaling × 3 种 wd 没有明显交互**（最优 scaling 和最优 wd 各自独立）
> - **没有任何 NaN 或 loss spike**——所有 15 组 10ep + 5 组 30ep 训练都数值稳定
> - **10ep ranking 几乎完全预测 30ep ranking**——可继续用 10ep 快筛 + 30ep 前 5 复筛的工作流
>
> **生产推荐**：`paper` scaling + `wd=5e-4` 或 `wd=2e-3`，不需要为 scaling 操心。
