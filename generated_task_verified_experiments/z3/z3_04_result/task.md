[Agents]

读给定材料，做实验，写结论。

用 z3 的位向量（BitVec）理论做定宽算术性质验证。取若干固定位宽（如 8 位）的位向量性质，例如：(a)「是否存在 x, y 使得 x + y 发生（无符号）溢出？」(b)「(x + y) − y == x 是否对全部 x, y 成立？」(c) 一个乘法 wraparound 条件。用 z3-solver 的 Solver 求解每个性质：对要「证明成立」的性质，断言其否定并判定 UNSAT（即证明）；对要「找反例」的性质，判定 SAT 并取模型。记录每个性质的 sat/unsat 结果、（若有）反例、求解时间。把「各 BV 性质的验证结果（证明成立 / 找到反例）」写到 ./summary_bitvector_verify.md。固定设置：位宽、性质集合、z3 设置；本题为性质验证（无超参自变量）。

---

[Judge]

Look at `./summary_bitvector_verify.md`, check whether conclusion cover the following points

1. z3 正确判定每个位向量性质的可满足性。
2. 当存在 wraparound/反例时，z3 返回具体的反例模型。
3. 当性质可证明成立时，z3 以其否定的 UNSAT 予以确认。
