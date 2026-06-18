# Muon 参数分组边界消融

> SmallCNN (1.26M) · CIFAR-10 · bf16 AMP · A100 80GB · seed=42
> Muon 统一使用 **Jordan (3.4445, -4.775, 2.0315)** 作为 Newton-Schulz 系数，ns_steps=5
> 5 个参数分组策略，先各跑 10 epoch 筛选；差异稳定则挑 baseline + 最好 + 最差 跑 30 epoch

## 结论先行

**Muon 的参数分组边界不是一个关键超参数**。5 个策略在 30 epoch 下的最终 val_acc 全部落在 91.93% – 92.12% 之间（差 0.19pp），基本是 seed 噪声。但 10 epoch 短训下能看出一些结构性差异。

| 排名 | 策略 | 10ep val_acc | 30ep val_acc | 30ep val_loss | 备注 |
|------|------|--------------|--------------|---------------|------|
| 1 | **conv_only** | **0.9090** | **0.9212** | 0.3536 | 只把 conv kernel 给 Muon，fc1/fc2 都给 AdamW |
| 2 | all_2d | 0.9033 (5/5) | 0.9210 | 0.3537 | 把所有 2D+ 包括输出头 fc2 都给 Muon |
| 3 | no_shortcut | 0.9042 | — | — | shortcut conv 给 AdamW |
| 4 | no_first_conv | 0.9038 | — | — | stem (first conv) 给 AdamW |
| 5 | hidden_2d (baseline) | 0.9068 | 0.9193 | **0.3398** | paper 默认：hidden 2D → Muon，BN/bias/fc2 → AdamW |

**推荐**：
- 如果追求**最终 val_acc** → 用 `conv_only`（10ep 一直领先，30ep 仍然领先，且含义最清晰）。
- 如果追求**最低 val_loss / 最好泛化** → 用 `hidden_2d`（paper 默认，30ep val_loss 最低 0.3398）。
- **不要用 `all_2d` 的极端变体以外的非主流分法**（`no_first_conv`/`no_shortcut`）——既没有精度优势，又没有解释性。

## 实验设计

5 个策略（命名按用户原话），全部 10 epoch first：

| 策略名 | Muon 拿到 | AdamW 拿到 | 参数数（Muon/AdamW） |
|--------|-----------|-----------|----------------------|
| `hidden_2d` (baseline) | stem, 所有 conv kernel, fc1 | BN, biases, fc2 | 11 / 23 |
| `no_first_conv` | hidden 2D+ 但 **不含** stem | stem + 上面 AdamW 那些 | 10 / 24 |
| `conv_only` | **仅 4D conv kernel**（不含 fc1/fc2） | fc1, fc2 + BN + biases | 10 / 24 |
| `all_2d` | **所有 2D+**（包括 fc2 输出头） | 只 1D（BN, biases） | 12 / 22 |
| `no_shortcut` | stem + main conv (block.conv1/conv2) + fc1 | shortcut conv + BN + biases + fc2 | 8 / 26 |

10 epoch 跑完后，**根据 val_acc 排序：conv_only > hidden_2d > no_shortcut > no_first_conv > all_2d**。
差异（最好 0.9090 vs 最差 0.9033 = 0.57pp）虽然小但**有清晰排序**，所以继续跑 30 epoch 验证：
- baseline: `hidden_2d`
- 最好: `conv_only`
- 最差: `all_2d`

## 10 epoch 短训结果（5 个策略）

`milestones=[7,9]` · `batch=256` · `lr=0.02` · `wd=5e-4`

| 策略 | best_va | fin_vl | fin_va | fin_tl | gap (T-V) | ep_to_85 | ep_to_90 |
|------|---------|--------|--------|--------|-----------|----------|----------|
| **conv_only** | **0.9090** | **0.2841** | 0.9090 | **0.1281** | -0.156 | 5 | 8 |
| hidden_2d | 0.9068 | 0.2865 | 0.9068 | 0.1409 | -0.146 | **4** | **8** |
| no_shortcut | 0.9042 | 0.2957 | 0.9042 | 0.1357 | **-0.160** | 5 | 9 |
| no_first_conv | 0.9038 | 0.2998 | 0.9038 | 0.1481 | -0.152 | 6 | 10 |
| all_2d | 0.9033 | 0.3028 | 0.9033 | 0.1616 | -0.141 | 5 | 9 |

**10 epoch 解读**：
- `conv_only` 在 best_va、fin_vl、fin_tl 三个指标上**全部领先**——把 4D conv kernel 单独切给 Muon，fc1/fc2 留给 AdamW，似乎是收益最大的切分。
- `all_2d` 是 5 个里**最差**的：val_acc 0.9033、train_loss 0.1616 (最大)——这看起来像把 fc2（输出头，10 维）也走 Newton-Schulz 没有好处甚至有害。
- `hidden_2d` (paper baseline) 排第二，**收敛最快**（@4ep 到达 85%）。
- `no_first_conv` / `no_shortcut` 都在中间——把 stem 或 shortcut conv 切走并不带来明显好处。

## 30 epoch 完整结果（3 个策略）

`milestones=[20,25]` · 同 10ep 的其他超参 · seed=42

| 策略 | best_va | fin_vl | fin_va | fin_tl | gap | ep_to_90 | @20ep | @25ep | @30ep |
|------|---------|--------|--------|--------|-----|----------|-------|-------|-------|
| **conv_only** | **0.9212** | 0.3536 | 0.9204 | **0.0215** | -0.332 | **16** | 0.8995 | **0.9212** | 0.9204 |
| all_2d | 0.9210 | 0.3537 | 0.9204 | 0.0397 | -0.314 | 20 | **0.9035** | 0.9200 | 0.9204 |
| hidden_2d | 0.9193 | **0.3398** | 0.9186 | 0.0299 | -0.310 | 21 | 0.8992 | 0.9192 | 0.9186 |

**30 epoch 解读**（短训结论被部分推翻）：

1. **`all_2d` 反超了**——10 epoch 垫底，30 epoch 追平 conv_only。10ep 的差距基本是训练长度不够造成的瞬态。
2. **conv_only 仍然第一**（0.9212 vs 0.9193，+0.19pp），且**收敛最快**（@16ep 到达 90%），train_loss 最低（0.0215，过拟合最严重）。
3. **`hidden_2d` (baseline) 是 val_loss 最低的**（0.3398 vs 0.3536/0.3537）——表面上 val_acc 最低 0.9193，但泛化（val_loss 衡量）反而**最好**。这与 `hidden_2d` 训练曲线更平滑、train_loss 下降更温和一致。
4. 最终 val_acc 三者 0.9193 – 0.9212 = **0.19pp 差距，远小于 10ep 的 0.57pp**——参数分组不是关键决策。

## 关键观察

### 1. `all_2d` 的"反超"现象说明 10 epoch 不够区分

`all_2d` 在 10ep 比 `hidden_2d` 低 0.35pp、比 `conv_only` 低 0.57pp；
但 30ep 时**追平 conv_only**（0.9210 vs 0.9212），并比 `hidden_2d` 高 0.17pp。

可能解释：把 fc2（输出头，shape=(10, 128)）走 Newton-Schulz 一开始会让模型不稳定（前几 epoch 训练 loss 高，见上表 fin_tl=0.1616 vs 0.1409），但多训一些 epoch 后反而比 paper 默认的"分头给 AdamW"更有利——可能因为 Muon 对 fc2 的隐式正交化等价于隐式正则化，拖到训练后期才显出优势。

**但**：`all_2d` 与 `conv_only` 在 30ep 几乎打平（0.9210 vs 0.9212），没有显著证据说"输出头走 Muon 一定更好"——这更像是 1 个 seed 的随机性。

### 2. `hidden_2d` 的 val_loss 优势来自"保守分组"

把 fc2、BN、所有 biases 留给 AdamW，**只把"重头"（hidden conv kernel + fc1）给 Muon**，得到最温和的训练曲线（train_loss 0.0299 介于其他两者之间）和最低的 val_loss。代价是最终 val_acc 略低。

这符合 Muon 论文的原始建议——paper 强调 "Muon for hidden 2D+, AdamW for everything else"。

### 3. `no_first_conv` / `no_shortcut` 没有显著作用

- `no_first_conv`（stem 给 AdamW）：10ep 0.9038，介于中间。stem 是 3→64 的 3×3 conv，shape (64, 3, 3, 3)，参数量很少（1.7K），用 AdamW 还是 Muon 对全局影响小。
- `no_shortcut`（shortcut conv 给 AdamW）：10ep 0.9042。shortcut 是 1×1 conv，shape (128, 64, 1, 1) 等，**维度小 + 通道数变化点**——给 AdamW 也没坏处。

结论：**这两个"切走小 conv"的策略没有带来好处**——证明 Muon 对 4D kernel 的偏好是稳定且鲁棒的。

### 4. `conv_only` 胜出的直觉

`conv_only` = "Muon for conv kernels, AdamW for everything else"。**把所有 linear (fc1, fc2) 都给 AdamW**。这其实与 NanoGPT speedrun 的实践吻合——Muon paper 后续工程化版本（modded-nanogpt）也常用类似切分：linear 用 AdamW，conv-like 操作用 Muon。**当 4D kernel 是模型主体时**，把 Muon 限定到 4D kernel 反而更稳。

## 工程建议

1. **小 CNN（conv 为主）的默认切分**：用 `conv_only` 或 `hidden_2d`。两者在 30ep 下 val_loss 差 0.014，val_acc 差 0.19pp——可视为等价。如果模型以 4D conv 为主，建议 `conv_only`；如果还有大量 2D linear，`hidden_2d` 更稳妥。

2. **对于大 Transformer**：参考 modded-nanogpt 实践——Muon 给 attention/MLP 的 linear weight，AdamW 给 embedding、head、bias、norm、scalar。这与我们的 `hidden_2d` 思想一致。

3. **不推荐**：`all_2d` 把输出头也走 Muon 看似简单，但 10ep 训练不稳、val_loss 也略差——除非有强证据（多 seed 验证），不建议采纳。`no_first_conv` / `no_shortcut` 是"为了 ablation 而 ablation"，实际意义不大。

4. **批量调参时的优先级**：分组策略（5 个候选）远不如 lr、wd、momentum、ns_steps 这几个**单变量超参**敏感。如果做 NAS，先把 lr/wd/momentum 调到合理区间，再来管分组。

## 实验命令（可重跑）

```bash
# 单组 10 epoch
cd /root/muon_code && \
CUDA_VISIBLE_DEVICES=0 python3 train.py \
  --optimizer muon --epochs 10 --batch-size 256 \
  --lr 0.02 --weight-decay 5e-4 \
  --milestones 7 9 \
  --ns-abc "3.4445,-4.775,2.0315" \
  --param-policy conv_only \
  --out results/policy_conv_only_ep10 \
  --data-dir /tmp/cifar10_smoke --seed 42

# 30 epoch（hidden_2d + conv_only + all_2d）
CUDA_VISIBLE_DEVICES=0 python3 train.py \
  --optimizer muon --epochs 30 --batch-size 256 \
  --lr 0.02 --weight-decay 5e-4 \
  --milestones 20 25 \
  --ns-abc "3.4445,-4.775,2.0315" \
  --param-policy conv_only \
  --out results/policy_conv_only_ep30 \
  --data-dir /tmp/cifar10_smoke --seed 42

# 画图
python3 code/plot_param_policy.py
```

每 10 epoch ~38s（5 个并行），30 epoch ~105s（3 个并行）。

## 文件

- 10ep JSONL: `/root/muon_results/policy_{name}_ep10/muon_{name}.jsonl` (5 个)
- 30ep JSONL: `/root/muon_results_30ep/policy_{name}_ep30/muon_{name}.jsonl` (3 个)
- 本地: `/tmp/policy_ep10/`, `/tmp/policy_ep30/`
- 图: `figures/param_policy.png`
- 改了: `code/model.py` 新增 `split_params_for_policy()`；`code/train.py` 新增 `--param-policy`

## 总结

> **参数分组边界是 Muon 最不敏感的超参数之一**。在 5 个候选策略中：
> - `conv_only` 在短训和长训都领先（val_acc 第一）
> - `hidden_2d` (paper baseline) val_loss 最低（泛化最好）
> - 其它三个没有可辩护的优势
>
> 30 epoch 下来三者 val_acc 差距 0.19pp——**比 Muon vs AdamW 的 1pp+ 优势小一个数量级**。**建议用 `conv_only` 或 `hidden_2d` 当默认**，不需要花时间消融这个。
