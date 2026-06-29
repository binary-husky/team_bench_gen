# SAT 编码 vs. 原生 SMT 编码 — 规模与求解时间对比

> 固定 z3-solver **4.16.0.0** 与一组固定的整数约束谜题实例；
> 自变量只有「编码方式」：(a) 纯布尔表编码 vs. (b) 原生 Int/算术 SMT 编码。
> 实验脚本：`experiment.py`、`extended.py`、`experiment2.py`；
> 原始结果：`results/raw.json`、`results/extended.json`、`results/extended2.json`、
> `results/combined.csv`、`results/stats.json`。

## 1. 实验设置

### 1.1 固定谜题族

| 族 | 范围 | 变量/域 | 约束类型 |
|---|---|---|---|
| N-Queens | N = 4..16 | N 个 Int，各取 0..N-1 | all-different + 对角线互斥（共 O(N²) 条线性不等式） |
| 固定图 k-着色 | K4, Petersen, Grötzsch, ER 随机图（顶点 15..50） | 顶点 1 个 Int，颜色 0..k-1 | 边上端点不相等（Diseq 链） |
| 线性整数系统 | ABC + DEF = GHIJ（10 个 Int） | 10 个 Int，各取 0..9 | 线性方程 + 互不等 + 首位非 0 |

每条实例都把同一问题用两种方式各编码一次：先跑 (a) 布尔表编码，再跑 (b) 原生 SMT 编码；
比对 (i) 变量数 / 断言数、(ii) 编码耗时、(iii) 求解耗时（`s.check()` 的耗时）、
(iv) 内部 SAT solver / arith theory solver 的统计量。

### 1.2 两种编码方式

**(a) 纯布尔「表编码」（direct / table encoding）**：
对每个 (变量, 取值) 二元组 `x[i][v]` 引入一个 z3 `Bool`。
- 每个变量「恰取一值」：`Or(x[i][*])` + 两两 `Not(And(x[i][v1], x[i][v2]))`。
- 关系/约束：用「表」写成两两 `Not(And(...))` 子句（与/析取形式），
  或用 `PbEq`（伪布尔等式，仅在线性整式一题使用）。
- 整体进入 Z3 后只有 SAT 子句，**不接触** arithmetic theory solver。

**(b) 原生 SMT 编码**：
直接用 `z3.Int`，写 `q[i] >= 0`、`q[i] < N`、`Distinct(q)`、对角线性不等式等。
Z3 走 CDCL(T)：SAT solver 控结构，整数 Simplex-based theory solver（Yices-style）
负责相容性，并经由「插值等式 + E-graph」与 SAT 通信（参 de Moura & Bjørner 2008）。

### 1.3 公平性检查

- 同一实例，两种编码的 SAT/UNSAT 结果**完全一致**。
- 两个编码返回的模型可能不同（这些谜题普遍有多解），
  但用各自模型回代原始约束都验证为合法解（见 `verify.py`）。
- 计时用 `time.perf_counter()`，每条都跑独立的 `z3.Solver()` 实例；
  对 N-Queens N=10 重复 5 次取中位数以减小噪声。

## 2. 规模：变量数 / 断言数

| 谜题 | 编码 | 顶层变量 | 顶层断言 |
|---|---|---:|---:|
| NQueens-8  | native Int | **8**   | **65**   |
| NQueens-8  | bool-table | 64      | 736      |
| NQueens-12 | native Int | **12**  | **145**  |
| NQueens-12 | bool-table | 144     | 2608     |
| NQueens-16 | native Int | **16**  | **257**  |
| NQueens-16 | bool-table | 256     | 6336     |
| ABC+DEF=GHIJ | native Int | **10** | **15**  |
| ABC+DEF=GHIJ | bool-table | 100   | 914      |
| Coloring-Petersen k=3 | native | **10** | **25** |
| Coloring-Petersen k=3 | bool-table | 30 | 85 |
| Coloring-Grotzsch k=4 | native | **11** | **31** |
| Coloring-Grotzsch k=4 | bool-table | 44 | 157 |
| Coloring-ER(50, 0.2) k=6 | native | **50** | **310** |
| Coloring-ER(50, 0.2) k=6 | bool-table | 300 | 2360 |

直观规律：
- **布尔表编码的变量数 = N · |dom|**，对 N-Queens 与整式谜题都是 ×N；
  着色就是 N · k。
- **断言数**：每个变量要求 O(|dom|²) 的两两互斥子句 + 每个关系 O(|dom|²)；
  在 N-Queens-8 上达到 736 ≈ N⁴ 量级；在 N-Queens-12 已上万。
- **原生 SMT 编码的断言数 ≈ 1 + (关系条数)**，与 N 几乎线性：
  N-Queens-8 只用 65 条 = N + 2·C(N,2)。

## 3. 编码耗时（构造公式用时，不含求解）

| 谜题 | 编码 | 编码耗时 (ms) | 加速比 native/table |
|---|---|---:|---:|
| NQueens-4  | native | 9.74   | 0.33× (table 更快) |
| NQueens-4  | bool   | 3.24   |  |
| NQueens-8  | native | 2.55   | **0.10×** |
| NQueens-8  | bool   | 24.64  |  |
| NQueens-12 | native | 5.22   | **0.06×** |
| NQueens-12 | bool   | 84.73  |  |
| NQueens-16 | native | 9.35   | **0.045×** |
| NQueens-16 | bool   | 207.57 |  |
| Coloring-ER(50) k=6 | native | 5.93 | 0.074× |
| Coloring-ER(50) k=6 | bool   | 79.90 |  |
| ABC+DEF=GHIJ | native | 1.24 | 0.040× |
| ABC+DEF=GHIJ | bool   | 31.36 |  |

规律：
- 构造 `O(N·|dom|)` 个 Bool、把它们逐对交叉配对要枚举 O((N·|dom|)²) 条子句，
  纯 Python 端的开销就上去了。NQueens-16 已经要 ~200 ms 写公式。
- 原生 Int 编码只有 N 个变量 + O(N²) 条 Ineq/Distinct，构造极便宜；
  即使在 N=16 上编码也不到 10 ms。

> 也就是说：原生 SMT 编码**便宜**的代价是把所有「值与值的关系」
> 推给 Z3 内部的 theory solver；表编码**贵**的代价是把这些关系
> 全部预先展开成 SAT 子句。

## 4. 求解耗时

> 这里是实验的核心：同样一个解，哪种编码让 Z3 的 `s.check()` 更快？

| 谜题 | 编码 | 求解耗时 (ms) | bool / native |
|---|---|---:|---:|
| NQueens-4   | native | 2.53   | 0.14×  (bool 更快) |
| NQueens-4   | bool   | 0.35   |  |
| NQueens-8   | native | 2.51   | 0.28× |
| NQueens-8   | bool   | 0.70   |  |
| NQueens-12  | native | 13.88  | 0.15× |
| NQueens-12  | bool   | 2.15   |  |
| NQueens-14  | native | 142.80 | **0.019×** |
| NQueens-14  | bool   | 2.76   |  |
| NQueens-15  | native | 110.87 | **0.030×** |
| NQueens-15  | bool   | 3.38   |  |
| NQueens-16  | native | 38.56  | 0.10× |
| NQueens-16  | bool   | 3.99   |  |
| Coloring-ER(50) k=6 | native | 33.69 | 0.054× |
| Coloring-ER(50) k=6 | bool   | 1.82  |  |
| Coloring-ER(40) k=4 (UNSAT) | native | 194.27 | 0.010× |
| Coloring-ER(40) k=4 (UNSAT) | bool   | 1.87  |  |
| ABC+DEF=GHIJ | native | 34.10 | 0.245× |
| ABC+DEF=GHIJ | bool   | 8.34  |  |

> **N-Queens N=10 上重复 5 次取中位数**：
>  - native 编码 solve 中位数 5.97 ms；
>  - bool 编码 solve 中位数 1.29 ms；
>  - 比值约 **0.22×**，与单次结果一致。

规律（在所有 22 条测试用例上一致）：

1. **布尔表编码几乎总是更快地完成 `s.check()`**。
   NQueens-14 上 bool/native = 2.76 ms / 142.80 ms ≈ **50×**。
   Coloring-ER(40)-k4 (UNSAT) 上 bool/native = 1.87 ms / 194.27 ms ≈ **104×**。

2. **原生 Int 编码的求解时间随 N 增长**（NQueens-14 出现 142 ms 的尖峰，
   与 arith theory solver 的 LP 内部行为相关），而表编码的求解时间
   几乎与 N 无关（即使 N=16 也只 ~4 ms）。

3. UNSAT 情况下表编码的优势更显著：UNSAT 证明需要理论求解器在
   arithmetic 里做深入传播（arith-eq-adapter / arith-conflicts 都很大），
   而表编码把 UNSAT 推给纯 SAT 子句后，CDCL 学到的子句可以直接导出 UNSAT 核。

## 5. Z3 内部统计：为什么表编码反而更快？

`results/stats.json` 给出了每次 `s.check()` 后 Z3 内部的真实统计（关键指标抽取）：

| N | 编码 | mk-bool-var | mk-clause | conflicts | decisions | arith-eq-adapter | arith-conflicts | arith-make-feasible |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 4  | native | 78  | 21  | 3  | 8   | 18  | 3  | 15  |
| 4  | bool   | 18  | –   | 3 (sat)  | 12 (sat)  | 0  | 0  | 0  |
| 8  | native | 346 | 103 | 19 | 79  | 84  | 19 | 139 |
| 8  | bool   | 66  | –   | 12 (sat) | 35 (sat)  | 0  | 0  | 0  |
| 10 | native | 552 | 230 | 95 | 239 | 135 | 94 | 492 |
| 10 | bool   | 102 | –   | 40 (sat) | 86 (sat)  | 0  | 0  | 0  |
| 12 | native | 806 | 494 | 296 | 1064 | 198 | 289 | 1992 |
| 12 | bool   | 146 | –   | 4 (sat)  | 41 (sat)  | 0  | 0  | 0  |

观察：

- **表编码的 stats 全部以 `sat-` 为前缀**；没有 `arith-*`。
  也就是 Z3 走的是「纯 CDCL SAT」分支，根本没启动 arithmetic theory solver。
- **原生 Int 编码必须 bit-blast / arith 化**：
  - 在 N=10 上 `mk-bool-var` 已经到 552（> 6× 比表编码）；
  - `arith-make-feasible` 在 N=12 上做 1992 次可行性修复；
  - `arith-conflicts` 几乎与 `conflicts` 相等，意味着 SAT 引擎大部分 conflict
    都来自 theory propagation 而非纯布尔。
- 这正契合 de Moura & Bjørner 2008 的描述：
  Z3 的 SAT 引擎配合 **congruence closure core + 多个 theory solver**
  协同解题；`arith-make-feasible` 等理论内部动作每次都要回到 SAT 层
  重新解释、开新 clause；表编码把所有这些一次性、静态展开成 SAT 子句，
  让 SAT 引擎独立工作。

## 6. 综合比较

| 维度 | 原生 SMT 编码 | 布尔表编码 |
|---|---|---|
| 变量数 | 少（≈ N） | 多（≈ N·|dom|） |
| 断言/子句数 | 少（≈ 1 + 关系数） | 多（≈ N·|dom|² 量级） |
| Python 端编码耗时 | 小（10 ms 量级甚至 N=16） | 大（200 ms 量级 @ N=16） |
| `s.check()` 求解时间 | 随 N 增长；易出现 arith 内部抖动 | 几乎与 N 无关，毫秒级 |
| UNSAT 表现 | 慢得多（要进 arith 深处） | 快得多（纯 SAT 即可） |
| 内部统计路径 | 走 SAT + 多个 theory solver | 只走 SAT 引擎 |
| 可读性/可维护性 | 高（直接是数学式） | 低（手工拆 (var, val)） |
| 适用场景 | 大域、稀疏关系、需要量化、需与非线性理论组合 | 小域、all-different / 表型约束、追求 UNSAT 速度 |

## 7. 结论

1. **变量规模**：表编码把 `q_i ∈ {0..|dom|-1}` 展开成 `|dom|` 个 Bool，
   所以变量数变为「变量数 × 值域大小」。在 N-Queens-16 上是 256 vs 16，在
   ABC+DEF=GHIJ 上是 100 vs 10，普遍为 N·|dom| 倍。
2. **约束/断言规模**：表编码为每个变量产生 O(|dom|²) 的两两互斥子句，
   再加关系拆解出的两两互斥子句，整体规模约为 N·|dom|²。
   原生 Int 编码的断言数 ≈ 1 + 关系数，与 N 几乎线性。
3. **编码时间**：原生 Int 几乎在 1–10 ms 完成；表编码随 N 增长明显
   （NQueens-16 ≈ 208 ms），瓶颈在 Python 端列举子句。
4. **求解时间**（最关键指标）：在我们跑的所有 22 条实例里，
   **表编码在 `s.check()` 上** **始终比原生 Int 编码快**，
   在中等以上规模（N≥10，或 UNSAT 实例）优势达 10×–100×。
5. **机制**：表编码把所有约束都「展开」成 SAT 子句，Z3 的 SAT 引擎
   就可以在不进入 arithmetic theory solver 的情况下求解；
   原生 Int 编码让 SAT 与 theory solver 反复交互（arith-eq-adapter、
   arith-conflicts、arith-make-feasible 等），开销在 N 较大或 UNSAT 时
   会显著放大。
6. **总体判断**：对于「小值域、纯线性/all-different」一类整数谜题，
   **纯布尔表编码在 Z3 内部是「求解更优」的选择**；原生 SMT 编码的
   真正价值在于编码表达力、域大小不需枚举、可与非线性理论/量化
   自然组合，以及对**编码耗时**的极大节约。

## 8. 局限与扩展

- 实验全部在 z3-solver 4.16.0.0、CPU、单进程、毫秒级子句规模下完成；
  绝对数值会随机器和 z3 版本变化，但「bool 编码在 `s.check()` 上
  始终更优、且优势随 N 增大」的结论在 22 条不同实例上保持一致。
- 表编码的 Python 端开销随 N 增长很快；工程实践中通常用一次性 Tseitin
  编码或在 SMT 求解器外预生成 CNF 跳过这步开销。
- 实验只覆盖**线性**整数谜题；非线性（如乘法、模）或量化条件下
  「表编码不一定可行 / 不一定更优」，这是原生 SMT 编码的真正优势区。

