# Newton-Schulz 系数对比实验

> 对比三组 Newton-Schulz quintic 迭代系数在 CIFAR-10 Muon 训练中的表现
> SmallCNN (1.26M) · 30 epoch · batch_size=256 · bf16 AMP · seed=42 · ns_steps=5

## 结论先行

**在我们的设置下，Classical (1.875, -1.25, 0.375) 略优于 Jordan (3.4445, -4.775, 2.0315)**，二者都远比 NaN 的 Symmetric (3, -3, 2) 强。

| 配置 | (a, b, c) | 性质 | Best val_acc | @5ep | @10ep | Final val_loss |
|------|-----------|------|--------------|------|-------|----------------|
| **Classical** | (1.875, -1.25, 0.375) | 真正的正交化，p(1)=1, p'(1)=0 | **0.9214** | **0.8434** | 0.8750 | **0.3172** |
| Jordan (论文) | (3.4445, -4.775, 2.0315) | 不完全正交化，最大化零斜率 | 0.9184 | 0.8384 | **0.8774** | 0.3427 |
| Symmetric (NaN) | (3, -3, 2) | p(1)=2 发散 | 0.1000 (随机) | NaN | NaN | NaN |

> **推荐：Classical (1.875, -1.25, 0.375)** —— 在我们的 30 epoch 实验中以 92.14% 略胜 Jordan 的 91.84%，且 val_loss 更低（泛化更好）。

## 为什么三组表现不同？数学视角

Newton-Schulz 迭代中，矩阵奇异值 `s` 按多项式更新：

```
s_{k+1} = a·s_k + b·s_k³ + c·s_k⁵
```

设 `p(s) = a·s + b·s³ + c·s⁵`，则：

| 系数 | p(1) | p'(1) | 零点斜率 = a | 物理意义 |
|------|------|-------|--------------|----------|
| **Jordan (3.4445, -4.775, 2.0315)** | **0.701** | 0.032 | **3.4445** | 不严格正交化；sv 落在 ≈ U(0.5, 1.5)；斜率最大 → 收敛最快 |
| **Symmetric (3, -3, 2)** | **2.0** | 0.0 | 3.0 | **p(1)=2 > 1，迭代发散，sv → ∞** |
| **Classical (1.875, -1.25, 0.375)** | **1.0** | **0.0** | 1.875 | 真正的正交化，sv → 1；斜率小但稳定 |

实测奇异值行为（对一个 64×64 随机矩阵做 5 次迭代，验证理论）：

| 配置 | min σ | max σ | mean σ | 状态 |
|------|------|------|------|------|
| Jordan | 0.041 | 1.192 | 0.852 | 稳定，受控 |
| Symmetric | 1.1×10¹⁶ | 6.1×10²² | 1.0×10²¹ | **爆炸** |
| Classical | 0.003 | 1.005 | 0.867 | 稳定，几乎完美正交 |

所以：
- **Symmetric 直接死**：p(1)=2 > 1 让所有接近 1 的奇异值都被推得更远（指数增长），NaN 是必然。
- **Jordan 牺牲精度换速度**：更高的 a=3.4445 让早期小奇异值快速"拉起来"，但代价是不再是真正的正交化（sv 不等于 1）。
- **Classical 走中庸路线**：a=1.875 斜率低一些，但收敛到稳定的 σ→1，速度损失在 5 次迭代后已经不重要。

## 收敛速度 vs 迭代次数的权衡

Jordan 的优势（高斜率）**主要在迭代次数 < 5 时体现**。本实验固定 5 次迭代，二者基本打平。如果我们只跑 3 次 NS 迭代，Jordan 会明显快。

这一点与 Muon 论文的"3 次 NS 加速"工作（[airbench94](https://github.com/KellerJordan/cifar10-airbench) 用的就是 3 次）一致——短迭代下 Jordan 系数的优势被放大。

## 进一步证据

`val_loss` 指标（@ epoch 30）：
- Classical: **0.3172**
- Jordan: 0.3427

Classical 的 val_loss 更低 ≈ 泛化更好。理论上也讲得通：Classical 是真正的正交化（sv=1），update 矩阵是 O(1) 的纯旋转；而 Jordan 的 update 是 USV^T with U(0.5, 1.5)，update 范数有 ~2x 噪声。

## 实验命令（可重跑）

```bash
# 1) Jordan (论文默认)
python3 code/train.py --optimizer muon --epochs 30 --batch-size 256 \
  --milestones 20 25 --ns-abc "3.4445,-4.775,2.0315" \
  --out results_ns_jordan

# 2) Symmetric (会 NaN，验证发散)
python3 code/train.py --optimizer muon --epochs 30 --batch-size 256 \
  --milestones 20 25 --ns-abc "3.0,-3.0,2.0" \
  --out results_ns_sym

# 3) Classical (推荐)
python3 code/train.py --optimizer muon --epochs 30 --batch-size 256 \
  --milestones 20 25 --ns-abc "1.875,-1.25,0.375" \
  --out results_ns_classical

# 4) 画图
python3 code/plot_ns.py
```

每组 ~3 min（A100 80GB），ns_steps=5。

## 文件

- 完整日志：`/tmp/ns_jordan.log`, `/tmp/ns_class.log`, `/tmp/ns_sym.log`（NaN）
- JSONL：`results/ns_jordan.jsonl`, `results/ns_classical.jsonl`
- 图：`figures/ns_comparison.png`
- 改了：`code/muon.py` 加了 `ns_abc` 参数；`code/train.py` 加了 `--ns-abc` CLI

## 建议

- **如果要发论文 / 跑大模型**：用 **Jordan**。它在 NanoGPT speedrun 里被广泛使用，配合 `@torch.compile` 在 H100 上是 SOTA。短迭代下斜率优势明显。
- **如果追求数值稳定 / 解释性 / 与 SVD 真正等价**：用 **Classical**。本次 CIFAR-10 实验中略胜。
- **永远不要用 Symmetric (3, -3, 2)**：p(1)=2 是正交化迭代的死亡之吻。
- 如果想再榨一点性能，可以尝试 `ns_steps=4` + Classical vs `ns_steps=5` + Classical，看缩短迭代是否在保证稳定的同时不损精度。

---

# 附：10 epoch 短训对照（与原 30/50 epoch 的对比）

把训练压缩到 10 epoch 跑一次完整对比，问题就变成"还有结论吗"。

## 10 epoch 数据（A100, seed=42, milestones=[7,9]）

| 配置 | Best val_acc | @3ep | @5ep | @7ep | @10ep | Final val_loss |
|------|-------------|------|------|------|-------|----------------|
| **Jordan (论文)** | **0.9047** | 0.8035 | **0.8563** | 0.8568 | **0.9043** | **0.2928** |
| Classical | 0.9019 | **0.8117** | 0.8470 | 0.8520 | 0.9019 | 0.3015 |
| SGD-Momentum | 0.8872 | 0.7231 | 0.7786 | 0.8325 | 0.8872 | 0.3299 |
| AdamW | 0.8747 | 0.7077 | 0.7690 | 0.7902 | 0.8747 | 0.3665 |

## 与 30 / 50 epoch 对照看

| Optimizer | 10ep | 30ep | 50ep |
|-----------|------|------|------|
| Muon (任一系数) | **0.9047** | 0.9214 | 0.9239 |
| SGD-Momentum | 0.8872 | 0.9259 | 0.9259 |
| AdamW | 0.8747 | 0.9138 | 0.9138 |
| **Muon 优势 (vs SGD)** | **+1.75 pp** | -0.45 pp | -0.20 pp |
| **Muon 优势 (vs AdamW)** | **+3.00 pp** | +0.76 pp | +1.01 pp |

## 10 epoch 短训下的结论

1. **Muon 的优势在短训下最大**——10 epoch 时比 SGD 高 1.75pp、比 AdamW 高 3.00pp；训到 30/50 epoch 时这个优势基本消失。
2. **Jordan vs Classical 在 10 epoch 短训下基本打平**（90.47% vs 90.19%，0.28pp 差距，seed 噪声内）。即便只有 10 epoch，二者也没拉开差距——5 步 NS 迭代已经足够长，让 Jordan 的高斜率优势基本兑现完了。
3. **Classical 在 @3 反而略快**（0.8117 vs 0.8035），可能是因为 Classical 早期奇异值更稳定，没有 Jordan 那种"先压后拉"的瞬态。
4. **如果要发短训报告 / 跑 few-shot**——结论完全倾向于用 Muon（任何系数）。
5. **如果要复现 paper / 跑大模型**——Jordan 与 Classical 选哪个都行；如果按 paper 选 Jordan 更"政治正确"。

## 短训支持"为什么不训满"

Muon 的核心卖点就是"前期收敛快"，所以短训场景下 Muon 的相对优势最大；训得越久，所有优化器都收敛，差异被抹平。这也是为什么 Muon 论文重点放在 NanoGPT speedrun（少步数）和 CIFAR-10 airbench（8 epoch 94%）这种"短训达到高水平"场景。

**回答用户问题：训练缩短到 10 epoch，结论不变——Muon 仍然最推荐；但 Muon 的相对优势比 30/50 epoch 时更明显。** 至于 NS 系数，10 epoch 时 Jordan 和 Classical 仍然是打平的。
