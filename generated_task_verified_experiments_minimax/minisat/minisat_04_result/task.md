[Agents]

读给定材料，做实验，写结论。

考察「鸽巢原理」这一结构性难例对求解器的影响。生成 PHP_n 的 CNF 编码：n+1 只鸽子放入 n 个洞——每只鸽子至少进一个洞（正子句），每个洞至多进一只鸽子（两两互斥的二文字子句）；该公式恒不可满足。取 n ∈ {3, 4, 5, 6, 7}，用 PySAT 的 MiniSAT 求解，记录每个 n 的冲突数与时间（注意 n=7 附近可能已很慢，必要时只取到能跑完的 n）。把「冲突数与时间随 n 的增长」写到 ./summary_pigeonhole.md。固定设置：上述 PHP 编码、n 取值、求解器；唯一自变量为 n。

---

[Judge]

Look at `./summary_pigeonhole.md`, check whether conclusion cover the following points

1. 冲突数与时间随 n 快速增长（超多项式/接近指数级）。
2. PHP 恒不可满足，求解器必须推导出完整反驳，无捷径。
3. 该快速增长与「鸽巢原理在分辨率证明系统下指数下界」相一致。


[Judge V2]

查阅 `./summary_pigeonhole.md` —— 基于真实实验结果对上方 [Judge] 的修订（以实测为准；PHP n=3..7）：

1. 须给冲突/时间随 n 快速增长（近指数）（golden：n 3→7 冲突比值 4.1/6.9/12.4/4.6×、时间 1/4/12.5/6.8×；可接受：超多项式增长）。（细化原 [Judge] 第 1 点）
2. 须给 PHP 恒不可满足、须推导完整反驳无捷径（可接受：点明 PHP UNSAT）。（细化原 [Judge] 第 2 点）
3. 须给与分辨率证明指数下界一致（可接受：点明一致）。（细化原 [Judge] 第 3 点）

<!-- judge-v2 authored-by: bcb94bc6 -->
