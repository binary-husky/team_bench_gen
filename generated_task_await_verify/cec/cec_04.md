[Agents]

复现 RCMAES 算法（./material），配置 python 环境。

研究 RCMAES 的另一个核心设计——adaptive restart 机制（论文 Algorithm 1 第 4–19 行）。固定种群缩减、active CMA、bound handling 等其他部分与 paper 默认一致。

至少对比以下 5 种 restart 策略，全部在 **CEC2022 D=20**（budget = 40000 evals）上跑：

1. `paper`：重启阈值 δ = (fmax-fmin)/max(|fmean|, 1e-12) ≤ 1e-8，新均值在上一收敛点周围 10% 边界长度的超矩形外采样
2. `no_restart`：完全禁用 restart，单次 CMA-ES 跑到底
3. `aggressive_restart`：阈值放松到 1e-6（更易触发重启）
4. `conservative_restart`：阈值收紧到 1e-10（极少触发重启）
5. `no_exclusion`：保持 paper 阈值，但新均值可在整个搜索空间任意采样（不排除已收敛区域）

每个策略在全部 12 个 CEC2022 D=20 函数上跑 25 次。

按函数类型分组（basic / hybrid / composition）报告平均 E、平均 restart 次数、平均收敛 epoch。

把结论写到 `./summary_restart.md`。

---

[Judge]

Look at `./summary_restart.md`, check whether conclusion cover the following points:

1. paper（带 10% exclusion 的 restart）在 hybrid 函数 F6-F9 上的 overall E 显著优于 no_restart（差距 ≥ 30%）
2. no_exclusion 比 paper 差（至少 60% 的 multimodal 函数 F6-F12 上 E 更大）
3. aggressive_restart（阈值 1e-6）在 basic 函数 F1-F5 上有负面效果（E 比 paper 高 ≥ 5%）
4. paper 的平均 restart 次数在 1.5–4.0 之间（既不过少也不过多），conservative_restart 的 restart 次数接近 0
