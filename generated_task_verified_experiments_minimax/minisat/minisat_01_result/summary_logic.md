# 为什么 CDCL 学习子句 C 之后，求解器不会再因当初使 C 被伪造的那组赋值而再次陷入冲突

下面这段推导仅基于 MiniSat 论文（Eén & Sörensson, "An Extensible SAT-solver", 2003）所描述的 CDCL 算法以及命题逻辑本身，不依赖任何额外的实验。

---

## 1. 一些预备：从 MiniSat 的 `analyze()` 看 C 是什么

当传播在某条「冲突子句」上发现所有文字都为 FALSE 时，进入冲突分析（论文 Fig. 10 的 `Solver::analyze`）：

```
out_learnt.push(0)            // 给断言文字预留位置
out_btlevel = 0
do
    p_reason.clear()
    confl.calcReason(this, p, p_reason)   // 让冲突子句给出"为 p 传播的原因"，
                                           //   第一次迭代时 p = ⊥_lit，理由就是冲突子句本身
    // 把原因里所有"在当前决策层上"出现的变量统计入 counter，
    // 把"在当前层以下、但层号 > 0"的变量记入 out_learnt，
    // 并把它们的决策层号 max 起来作为 out_btlevel
    for q in p_reason
        if !seen[var(q)]:
            seen[var(q)] = TRUE
            if level[var(q)] == decisionLevel(): counter++
            else if level[var(q)] > 0:          // 排除顶层假设
                out_learnt.push(~q)
                out_btlevel = max(out_btlevel, level[var(q)])
    p = trail.last()                              // 沿 trail 向前
    confl = reason[var(p)]
    undoOne()
while (--counter > 0)                             // 终止于 first-UIP
out_learnt[0] = ~p
```

由此得到的 `out_learnt` 就是学习子句 C，`out_btlevel` 就是**断言层 assertion level**。论文 Fig. 10 的后置条件明确写明：

> `out_learnt[0]` is the asserting literal at level `out_btlevel`.

`while (--counter > 0)` 这条终止条件，正是 first-UIP（First Unique Implication Point）切点的定义：在蕴含图上从冲突边反向广度优先展开，直到 current decision level 上只剩一个未访问的蕴含点为止。p 就是那个 UIP，`~p` 就是 C 的唯一在 current level 上的文字（也就是 C 的 asserting literal）。

---

## 2. (i) C 相对于原公式的逻辑地位：C 是 F 的逻辑推论

C 里的每一个文字 q，都是通过 `calcReason()` 在蕴含图上反向追溯某一次蕴含 p 时，从 p 的「理由子句」里取出来的：论文 §4（"Learning"）和 §4.4 写明，理由子句可以是：

- 一个用户给定的原始子句；或
- 一个先前已经被某个约束单元传播的子句（无论是原始的还是先前学到的）。

因此 C 里的每一个文字都来自一个**已经被原公式 F 蕴含的子句**。把这些理由子句在蕴含图上反复合取-消解（resolution），C 就是这些消解的合取，所以：

> **C 是 F 的逻辑推论**（C is a logical consequence of the original problem constraints）。

论文 §4 也明确写到：

> "This learnt clause must always, by construction, be implied by the original problem constraints."

把 C 加进子句库，等价于把 F 替换成 `F ∧ C`（在命题逻辑意义下不改变可满足性 — UNSAT 情况下仍然 UNSAT，SAT 情况下模型仍满足 F）。这是 (i) 的答案。

但仅有 (i) 还不够。**学习 C 本身并不能在结构上阻止"使 C 被伪造的那组赋值"再次出现** —— 假如求解器允许在断言层之上做出与之前完全相同的高层决策，并再次从该层出发按相同方式传播，就完全可能再次把 C 变 unit 的反方向、把 C 整条置假。真正的"不重复"保证来自 (ii)。

---

## 3. (ii) 在断言层上，结构上阻止那组冲突赋值再次出现的机制：asserting literal 的强制单元传播

设 L 是当前的冲突层（conflict level），A = `out_btlevel` 是 C 的断言层（即 C 中除 asserting literal 之外、文字所在决策层号的次大值）。first-UIP 切点的结构性质给出三件事：

1. C 在 L 层上**有且仅有一个**文字，那就是 asserting literal `a = ~UIP`。
2. C 在 A 层上**没有任何**文字 —— 换言之，除 asserting literal 之外，C 中所有文字的决策层都**严格小于 A**（因为 `out_btlevel` 是 C 中"非当前层"文字层号的最大值）。
3. 那些"非当前层"文字所在的层号都 ≤ A，其中有些可能在 A 层，也有些在更低的层。

### 3.1 回跳之后 C 的形状

调用 `cancelUntil(A)`（论文 Fig. 13 `search` 循环里）把 trail 截到 A 层：

- L 层上**所有**的赋值（含那个 UIP 自己的赋值）都被撤销；A 层之上**所有**的高层决策和被它们引发的传播赋值都被撤销。
- A 层和 A 层**以下**的所有赋值（也就是 C 中"非 asserting literal"那一组文字所在层的赋值）**被原封不动地保留**在 trail 上。

记 C 中除 asserting literal 之外的那组文字为 `R`（"reason literals"）。R 中每一个文字，在 trail 上仍然取冲突发生时让该文字为 FALSE 的那个值。因为我们只是把比 A 更浅的层之上的赋值撤销了，**比 A 更深的层被砍掉，R 的赋值纹丝不动**。

回跳完成时，trail 处于 A 层。此时 C 的形状是：

| C 的文字 | 取值 | 所在层 |
|---|---|---|
| asserting literal `a = ~UIP` | 未赋值 | (高于 A，将要由传播决定) |
| 每个 R 中的文字 `r` | **FALSE**（保留自旧 trail） | ≤ A |

即在 A 层上，C 中除 `a` 之外的所有文字都已经是 FALSE，C 在 A 层是一个**单元素未被赋值的子句**。

### 3.2 进入传播循环

回到 `search` 的主循环，调 `propagate()`。C 立刻成为 unit：把 `a` 入 propagation queue，`a` 被强制赋 TRUE（`enqueue` 在论文 Fig. 9 中立即处理）。这一步是**结构上不可避免**的：trail 已经被截到 A 层、C 中其它文字全部为 FALSE 是 trail 的事实，propagation queue 一旦扫到 C 就只能让 `a` 为 TRUE。

也就是说，**在 A 层，UIP 那个变量 x 的取值已经被强制翻转到与冲突时相反的值**（冲突时是 UIP=TRUE 致使 C 中该文字为 FALSE；现在是 `~UIP`=TRUE 致使 C 中该文字为 TRUE）。

### 3.3 这为什么在结构上排除了"当初使 C 被伪造的那组赋值"

那组「当初使 C 被伪造的赋值」在冲突时是这样的部分赋值 π：

- 对 C 中每个 `r ∈ R`：`var(r)` 的值是 π 在层 ≤ A 上给出的那一个，恰好让 `r`=FALSE；
- 对 `var(a)=x`（即 UIP 变量）：π 在层 L 上让 x=TRUE，从而使 `a=~UIP`=FALSE。

回跳 + 单元传播后，在同一 A 层上：

- `var(r)` 的值与 π 在该层上**完全一致**（trail 保留了 A 层及以下的赋值）；
- `var(x)` 的值**必然与 π 不同**（被强制翻转）。

于是，在 A 层这一"地基"上，赋值 π 不可能再被重建 —— 它所需的 x 的值已经在结构上被单元传播决定了，而单元传播所依据的只是 C 的形状和被保留的 trail，不依赖任何后续决策。

更重要的是：**CDCL 只在回跳到 A 层时才会重新探查 A 层之上的搜索空间**。在 A 层上，propagation 已经把 C 的 asserting literal `a` 强制为 TRUE，并把 x 翻到与 π 相反的值，因此**任何在 A 层之上的后续决策路线，只要在底层赋值上与 π 重合，就必然与 C 在 A 层上 (i) 被 propagate 出 `a`、以及 (ii) 翻转 x 这两件事相冲突**。换言之，"使 C 被伪造"的那个 A 层子赋值 π 在此后的搜索中已经是一个被 C 永久证伪的部分赋值。

### 3.4 顺带的结构后果

这一机制还顺带解释了一个不显然的事实：学习 C 之后，下一次冲突**只可能由 C 的一个真子赋值产生**。因为：

- C 中 R 部分仍可能在更高层被不同的决策再次"重新伪造"（更高层的决策改变 `var(r)` 的值，使 C 中 r 又为 FALSE）；
- 但 C 整条永远不会再被同一组 A-层子赋值 π 整条置假，因为 `a` 在 A 层就已被强制为 TRUE。

这正是 first-UIP 学习方案要比任意一个 1-UIP 切点的 resolvent 更强的地方 —— 它保证在 A 层（而非 L 层）就能让 C 变成 unit，从而回跳到 A 而非仅仅回跳到 L，把更多高层无用分支一并剪掉。

---

## 4. 把 (i) 和 (ii) 拼起来：不会因同一组赋值再次冲突的完整保证

把 (i) 和 (ii) 一起，就是所求的保证：

- **(i) C 本身就是 F 的逻辑推论**：C 是蕴含图上由若干理由子句（都是 F 的子句或先前学到的子句，它们自己又都是 F 的推论）反复消解出来的合取，因此 `F ⊨ C`。在子句库里加上 C 不丢失任何模型、也不引入伪模型，只是把搜索空间按 C 进一步收紧。
- **(ii) 在断言层 A 上是 asserting literal 的强制单元传播在结构上阻止了那组赋值**：`cancelUntil(A)` 把所有高于 A 层的赋值砍掉、保留 A 层及以下 trail 的事实；first-UIP 切点保证 C 在 A 层上没有文字、只有 asserting literal `a` 还在未定；这两条一起意味着回跳到 A 后，C 在 A 层上变成 unit，`a` 被 propagation 立即强制为 TRUE，从而 UIP 变量 x 在 A 层上的取值被**结构性翻转**，与冲突时的取值相反。CDCL 接下来任何在 A 层之上的分支路线，底层子赋值都不可能再与"当初使 C 被伪造"的那一组一致 —— 因为那组赋值在 A 层上的"指纹"已经被 (ii) 永久改写。

因此，**学习 C 之后所避免的不是任意冲突，而是那一个特定的、由 C 在 A 层上的子赋值所代表的冲突**。这正是 first-UIP + 非时序回跳 (non-chronological backtracking) 整个机制想要达到的"剪枝"目标 —— 而这一保证严格地来自 (i) C 的逻辑身份与 (ii) 断言层上 asserting literal 的强制单元传播这两件事的合力。
