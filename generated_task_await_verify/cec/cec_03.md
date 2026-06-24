[Agents]

复现 RCMAES 算法（./material），配置 python 环境。

研究 RCMAES 最核心的设计选择——维度依赖的非线性种群缩减调度（论文式 6–9）。固定其他超参与 paper 默认一致，只改变 Np(t) 的缩减形式。

至少对比以下 5 种 population reduction schedule，全部在 **CEC2022 D=20**（budget = 40000 evals）上跑：

1. `paper`：Np(t) = N0 - (N0 - D)·[1 - (1-t)^r]，r = 1.7 - 0.01·D（D=20 时 r=1.5）
2. `linear`：r = 1.0（线性缩减，等价于 LSHADE 风格）
3. `aggressive`：r = 2.5（远高于 paper 的非线性更激进）
4. `conservative`：r = 0.5（比线性更慢的缩减）
5. `constant`：完全不缩减，Np(t) ≡ N0

每个 schedule 在全部 12 个 CEC2022 D=20 函数上跑 25 次。

按函数类型分组（basic F1-F5 / hybrid F6-F9 / composition F10-F12）报告平均 E 值。

把结论写到 `./summary_pop_reduction.md`。

---

[Judge]

Look at `./summary_pop_reduction.md`, check whether conclusion cover the following points:

1. paper 默认（r=1.5）在 overall E 上排第 1 或与第 1 差距 ≤ 5%
2. constant（无缩减）在 composition 函数 F10-F12 上显著差于 paper（E 差距 ≥ 30%）
3. linear（r=1.0）略差于 paper 的非线性（overall E 差距 ≥ 5%）
4. aggressive（r=2.5）在 multimodal 函数上出现早熟收敛征兆（至少 4/12 函数的最终 E 比 paper 高 ≥ 50%）
