[Agents]

复现 muon 在 cifar-10 上面的实验，自行查阅论文（./material），配置python环境，训练 30 epoch。

对比 Newton-Schulz quintic iteration 中 a, b, c = (3.4445, -4.7750, 2.0315)、 a, b, c = (3.0000, -3.0000, 2.0000)、 （a=1.875,b=−1.25,c=0.375）的效果区别

把在该实验中的更优者写到 ./summary.md 中，如果有其他发现，也写在 ./summary.md 里面

---

[Judge (IQ requirement: low-IQ)]

Look at `./summary.md`, check whether conclusion cover the following points

1. 在我们的设置下，Classical (1.875, -1.25, 0.375) 略优于 Jordan (3.4445, -4.775, 2.0315)
2. 二者都远比 NaN 的 Symmetric (3, -3, 2) 强。
