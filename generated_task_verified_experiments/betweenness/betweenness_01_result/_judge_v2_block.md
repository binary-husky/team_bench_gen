Look at `./summary_betweenness_01_accumulation.md` — REAL verdict (measured by execution; supersedes the conjectured [Judge] above):

1. **(a) `σ[v]/σ[w]` 含义**：答案用双射论证证明——每条 `s→v` 最路接上边 `(v,w)`（长度 `d(s,v)+1=d(s,w)`，确为最短）一一对应一条"以 `(v,w)` 收尾"的 `s→w` 最路，反之去掉 `(v,w)` 即还原；故"经过 `v` 的 `s→w` 最路数"`=σ_sv`，总数`=σ_sw`，比值 `σ_sv/σ_sw` 恰为对依赖 `δ_sw(v)`；并由 Bellman 准则 `σ_sw(v)=σ_sv·σ_ww=σ_sv·1=σ_sv` 收尾。(confirms original [Judge] point 1a)

2. **(b) `(1+δ[w])` 拆分**：答案明确 `1` 对应终点 `t=w` 时 `v` 的贡献，即 `δ_sw(v)=σ_sv/σ_sw`；`δ_s•(w)=Σ_t δ_st(w)`（因 `δ_sw(w)=0`，求和只含下游 `t≠w`），并给出乘法可分式 `δ_st(v,{v,w})=(σ_sv/σ_sw)·δ_st(w)`，对所有下游 `t` 求和后提出公因子得 `(σ_sv/σ_sw)·δ_s•(w)`——即把 `Θ(n²)` 个对依赖塌缩为 `n` 个标量。(confirms original [Judge] point 1b)

3. **(c) 反向扫描 + O(nm) 结论**：答案指出后继满足 `d(s,w)=d(s,v)+1>d(s,v)`，故更远的 `w` 必须先于 `v` 算完；BFS 按距离非递减出队、压栈 `S`，逆序弹出即按距离非递增（最路 DAG 的逆拓扑序），天然满足递推依赖。最终每源一次 BFS `O(m)` + 一次反向累加 `O(m)` = `O(m)`，`n` 个源共 `O(n·m)`、空间 `O(n+m)`；而朴素 summation 步骤是 `Θ(n³)` 时间、`Θ(n²)` 空间瓶颈，故无法企及 `O(nm)`。(confirms original [Judge] point 1c)
