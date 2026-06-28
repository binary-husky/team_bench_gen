[Agents]

读给定材料，做实验，写结论。

考察同一约束问题用「纯布尔 SAT 编码」与「原生 SMT 理论编码」的差异。取一个小规模整数约束谜题（例如：若干取小范围值的 Int 变量满足一组线性约束/互不等，固定实例）。分别用 z3-solver (pip install z3-solver) 以两种方式编码并求解：(a) 纯布尔编码——用 z3 Bool 变量为每个(变量,取值)二元组建一个布尔变量、用析取/合取表达约束（表编码/bit枚举）；(b) 原生 SMT——直接用 z3 Int 与算术/关系运算。记录两种编码的变量数/约束数与求解时间。把「SAT 编码 vs 原生 SMT 的规模与时间对比」写到 ./summary_sat_vs_smt.md。固定设置：约束谜题实例、变量取值范围、z3 版本；自变量为编码方式。

---

[Judge]

Look at `./summary_sat_vs_smt.md`, check whether conclusion cover the following points

1. 原生 SMT 编码的规模（变量/约束数）远小于手工布尔 SAT 编码。
2. 求解时间相当或更快（理论推理避免了布尔爆炸）。
3. 体现原生理论推理相比全盘位爆破/布尔化的优势。
