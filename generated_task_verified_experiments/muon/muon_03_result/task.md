[Agents]

复现 muon 在 cifar-10 上面的实验（./material），配置python环境。

Muon 使用 Jordan (3.4445, -4.7750, 2.0315) 作为 Newton-Schulz 系数基准。训练 SmallCNN (1.26M) 至少 10 epoch。

研究 Muon 的参数分组边界：哪些参数应该用 Muon，哪些用 AdamW。

至少对比以下 5 个策略：
1. `hidden_2d` (paper 默认)：所有 hidden 2D+ → Muon；BN / biases / 分类头 → AdamW
2. `all_2d`：所有 2D+ 矩阵（含输出头） → Muon；BN / biases → AdamW
3. `conv_only`：只把 conv kernel → Muon；fc1/fc2 / BN / biases → AdamW
4. `no_first_conv`：`hidden_2d` 基础上额外把 stem conv → AdamW
5. `no_shortcut`：`hidden_2d` 基础上额外把 shortcut conv → AdamW

每个策略训练 10 epoch 快筛，挑 baseline + 最好 + 最差 跑 30 epoch。

把结论写到 `./summary_param_policy.md`。

---

[Judge]

Look at `./summary_param_policy.md`, check whether conclusion cover the following points:

1. 参数分组边界对 Muon 最终 val_acc 影响很小（30ep 下 5 个策略都落在 ~92% 区间内，差 ≤ 0.2pp）
2. 给出明确的推荐策略（例如 `conv_only` 取最高 val_acc，或 `hidden_2d` 取最低 val_loss），并解释为什么
3. 至少 1 张图比较 5 个策略在 10ep 下的 val_acc 或 val_loss