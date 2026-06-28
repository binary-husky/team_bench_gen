[Agents]

读给定材料，做实验，写结论。

自行复现 HyperLogLog 算法（从给定材料中的论文出发用 Python/numpy 实现；寄存器个数 m=2^p，p=14，完整原始估计 + 小/大范围修正）。

研究目标：**在固定 m 与 n 下，不同 64-bit 哈希族（mmh3 / xxhash / hashlib-blake2b / numpy random bits）对估计精度与常数因子的影响**——验证 §4.1 推导的 `SE = β_m/√m` 是否对哈希族近似稳健，或某些哈希族因混合 / 自相关导致 `β_m` 实际偏大。

固定实验设置（不要更改）：
- 算法：标准 HLL（m=2^14=16384 寄存器），p=14；其余参数（α_m、bias-correction、merge）按论文。
- 真实基数网格：`n ∈ {1e4, 1e5, 1e6}`。
- 哈希族（每族视为一个独立的 64-bit hash function 实现）：
  - `mmh3` (`mmh3.hash64(..., x64=True)`，seed=0)；
  - `xxhash` (`xxhash.xxh64(...).intdigest()`)；
  - `hashlib.blake2b` (取 `digest()` 前 8 字节再转 int)；
  - `numpy.random` (用 `default_rng(seed).integers(2**64, size=n, dtype=np.uint64)` 直接生成 64-bit 整数作为完美随机 ground truth)。
- 每个 `(哈希族, n)` 用 **≥ 10 个不同种子**独立重复（hash seed 决定哈希的随机性源；npy 用 generator seed），记录每次的相对误差 `|Ê-n|/n`。
- **仅 CPU**；整轮 **< 30 分钟**。
- 注：numpy.random 给的是完美的独立均匀 64-bit bit source，相当于"理论下界"对照；mmh3 / xxhash / blake2b 是真实常用哈希。

需要记录/报告的指标：
- 一张表：每个 `(哈希族, n)` 下相对误差的 **均值 ± 标准差**（跨种子）。
- 一张图 / 一列：把每个 n 下"该哈希族的均值"与"numpy-random 的均值"对比（差值 / 比值）。
- 简单结论：**经验 β_m_est = mean(|Ê-n|/n) * √m** 是否在不同哈希族下近似一致（差距 ≤ 2×）。

把以上写到 `./summary_hll_06_hash_family.md`。

---

[Judge]

Look at `./summary_hll_06_hash_family.md`, check whether conclusion covers the following points (≤ 3 points)

1. 给出了每个 `(哈希族 ∈ {mmh3, xxhash, blake2b, numpy.random}, n ∈ {1e4, 1e5, 1e6})` 组合下**经验相对误差的均值 ± 标准差**（≥ 10 种子），以表格或图呈现。
2. 对比各哈希族的 `β_m_est = mean(|Ê-n|/n) * √m`（在 n=1e5 或 1e6 上），指出**真实哈希族（mmh3/xxhash/blake2b）相对 numpy-random ground truth 的 β_m_est 偏大多少**（通常在 1.0–1.5 倍之内；若 ≥ 2× 则需说明原因）。
3. 明确指出**经验结论是否支撑 `SE = β_m/√m` 对哈希族稳健**的论点（结论若是"是"，需给各哈希族 β_m_est 的最大比值；若"否"，需指出哪一族明显差）。
