#!/usr/bin/env python3
"""
Lightweight z3 symbolic-execution / concolic framework (CPU-only, pip-only).

Goal: compare *symbolic execution (solving accumulated path constraints)* vs
*random fuzzing* at reaching a deep / rare TARGET branch in g(x).

Target function g(x):
    if x > 10 and x % 7 == 3 and x * 2 < 100:  <TARGET>
i.e. a multi-guard "needle" condition whose satisfying inputs occupy a
vanishingly small slice of the input space.
"""
import random
import z3

# ---- Concrete target function ----------------------------------------------
# Domain for concrete evaluation / fuzzing: 32-bit non-negative integers.
DOMAIN_BITS = 32
DOMAIN_SIZE = 1 << DOMAIN_BITS  # [0, 2^32)


def g(x):
    """Returns True if the deep TARGET branch is reached."""
    if x > 10 and x % 7 == 3 and x * 2 < 100:
        return True
    return False


# Ground-truth set of satisfying inputs (for sanity, not used by either method):
#   x>10, x*2<100 => 11 <= x <= 49 ; x%7==3 => x in {17,24,31,38,45}
# (only scan the bounded feasible window, NOT the whole 2^32 domain)
SATISFYING = [x for x in range(0, 100) if g(x)]
assert SATISFYING == [17, 24, 31, 38, 45], SATISFYING
TRUE_PROB = len(SATISFYING) / DOMAIN_SIZE  # ~2.33e-9


# ---- (a) Symbolic execution: accumulate PC, solve with z3 ------------------
def symbolic_exec():
    """Walk the path, accumulate each guard into the path condition PC, then
    ask z3 whether PC (incl. the TARGET branch condition) is satisfiable.
    Returns (found, n_solves, model_x)."""
    x = z3.Int('x')
    pc = []  # accumulated path constraints
    n_solves = 0

    # guard 1
    pc.append(x > 10)
    # guard 2
    pc.append(x % 7 == 3)
    # guard 3 (target-enabling)
    pc.append(x * 2 < 100)

    s = z3.Solver()
    s.add(pc)
    s.add(x >= 0, x < DOMAIN_SIZE)  # bound to the fuzzing domain
    n_solves += 1
    res = s.check()
    if res == z3.sat:
        m = s.model()
        xv = m[x].as_long()
        assert g(xv), "z3 model does not actually reach TARGET!"
        return True, n_solves, xv
    return False, n_solves, None


# ---- (b) Random fuzzing ----------------------------------------------------
def fuzz(seed, n):
    rng = random.Random(seed)
    hits = 0
    for _ in range(int(n)):
        x = rng.randrange(DOMAIN_SIZE)
        if g(x):
            hits += 1
    return hits


def main():
    print(f"Domain size = 2^{DOMAIN_BITS} = {DOMAIN_SIZE}")
    print(f"True satisfying inputs = {SATISFYING}")
    print(f"True hit probability  = {TRUE_PROB:.6e}  ({len(SATISFYING)}/{DOMAIN_SIZE})")
    print()

    # (a) Symbolic execution
    found, n_solves, mx = symbolic_exec()
    print("=== (a) Symbolic execution (z3) ===")
    print(f"  found TARGET input? {found}")
    print(f"  z3 solver calls    = {n_solves}")
    print(f"  model x            = {mx}")
    print()

    # (b) Random fuzzing, N in {1e3,1e4,1e5}, >=3 seeds
    Ns = [1000, 10000, 100000]
    seeds = [1, 2, 3]
    print("=== (b) Random fuzzing ===")
    print(f"  seeds = {seeds}")
    fuzz_results = {}  # N -> list of (seed, hits, rate)
    for N in Ns:
        per_seed = []
        for sd in seeds:
            h = fuzz(sd, N)
            rate = h / N
            per_seed.append((sd, h, rate))
            print(f"  N={N:<7d} seed={sd}  hits={h:<3d}  rate={rate:.6e}")
        total_hits = sum(p[1] for p in per_seed)
        agg_rate = total_hits / (N * len(seeds))
        fuzz_results[N] = dict(per_seed=per_seed, total_hits=total_hits,
                               agg_rate=agg_rate, any_hit=total_hits > 0)
        print(f"  N={N:<7d} AGGREGATE over {len(seeds)} seeds: "
              f"hits={total_hits}  rate={agg_rate:.6e}  "
              f"found={'YES' if total_hits>0 else 'NO'}")
        print()

    # ---- write summary -----------------------------------------------------
    write_summary(found, n_solves, mx, fuzz_results, seeds)


def write_summary(found, n_solves, mx, fuzz_results, seeds):
    lines = []
    lines.append("# KLEE-04: 符号执行 vs 随机 Fuzzing —— 到达深层 / 稀有目标分支能力对比\n")
    lines.append("## 实验设置\n")
    lines.append("- 框架：轻量 Python + `z3-solver` 符号执行 / concolic 框架（未安装 KLEE 本体，仅 CPU、仅 pip）。")
    lines.append("- 目标函数 `g(x)`，深层目标分支为累积多 guard 的“针”条件：")
    lines.append("  ```")
    lines.append("  if x > 10 and x % 7 == 3 and x * 2 < 100:  <TARGET>")
    lines.append("  ```")
    lines.append(f"- 输入域：32 位非负整数 `[0, 2^32)`，共 {DOMAIN_SIZE} 个取值。")
    lines.append(f"- 满足条件的真实输入 = {SATISFYING}，共 {len(SATISFYING)} 个；"
                 f"真实命中概率 = {TRUE_PROB:.6e}（{len(SATISFYING)}/{DOMAIN_SIZE}），占比极小。")
    lines.append(f"- 随机 fuzzing 重复种子：{seeds}（每个配置 ≥3 个不同种子）。\n")

    lines.append("## 1. 结果对比表\n")
    lines.append("| 方法 | 是否找到到达 TARGET 的输入 | 关键指标 |")
    lines.append("|---|---|---|")
    lines.append(f"| 符号执行 (z3 解 PC) | {'找到' if found else '未找到'} | "
                 f"z3 求解次数 = {n_solves}；模型 x = {mx} |")
    for N in sorted(fuzz_results):
        r = fuzz_results[N]
        lines.append(f"| 随机 fuzzing (N={N}) | {'找到' if r['any_hit'] else '未找到'} | "
                     f"命中数 = {r['total_hits']} / {N*len(seeds)}；"
                     f"命中率 = {r['agg_rate']:.6e} |")
    lines.append("")

    lines.append("### 随机 fuzzing 各 N / 各种子明细\n")
    lines.append("| N | seed | 命中数 | 命中率 |")
    lines.append("|---|---|---|---|")
    for N in sorted(fuzz_results):
        for sd, h, rate in fuzz_results[N]['per_seed']:
            lines.append(f"| {N} | {sd} | {h} | {rate:.6e} |")
    lines.append("")

    lines.append("## 2. 结论要点\n")
    lines.append(f"1. **符号执行确定性找到**到达 TARGET 的输入：沿路径把 `x>10`、`x%7==3`、"
                 f"`x*2<100` 三个 guard 累积进路径条件 PC，**只需 1 次 z3 求解**即可判定 PC 可满足，"
                 f"模型直接给出满足条件的输入 `x={mx}`（经验证确为 `{SATISFYING}` 之一）。"
                 f"约束求解把“在海量输入里找针”的问题归约为可满足性判定，命中是确定性的。\n")
    lines.append(f"2. **随机 fuzzing 在合理 N 下命中率极低甚至为 0**：在 1e3 / 1e4 / 1e5 三个量级、"
                 f"每个量级 3 个种子下，总命中数均为 "
                 f"{sum(fuzz_results[N]['total_hits'] for N in fuzz_results)}（命中率 ≈ "
                 f"{sum(fuzz_results[N]['total_hits'] for N in fuzz_results) / sum(N*len(seeds) for N in fuzz_results):.6e}），"
                 f"与真实命中概率 {TRUE_PROB:.6e} 一致——满足累积多 guard 条件的输入测度极小，"
                 f"纯随机采样在可承受的 N 内几乎不可能命中。\n")
    lines.append("3. **对比验证**：符号执行的约束求解能力可定向“反推”出满足深层累积约束的输入，"
                 "成本是少量（此处仅 1 次）z3 求解；而随机 fuzzing 受限于概率，"
                 "对测度极小的稀有目标分支本质上无能为力——这正是符号执行（如 KLEE）"
                 "相对于盲目 fuzzing 的核心优势：以约束求解换取对深层 / 稀有路径的可达性。\n")
    lines.append("---")
    lines.append("参考材料：Cadar, Dunbar, Engler (2008), *KLEE: Unassisted and Automatic "
                 "Generation of High-Coverage Tests for Complex Systems Programs*（见 `klee_material/`）。"
                 "KLEE 的核心即符号执行 + 约束求解以驱动覆盖深层分支，本实验以最小复现印证了其相对随机 fuzzing 的优势。")

    with open("summary_klee_04_deep_branch.md", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("wrote summary_klee_04_deep_branch.md")


if __name__ == "__main__":
    main()
