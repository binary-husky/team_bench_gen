Look at `./summary_betweenness_03_runtime.md` — REAL verdict (measured by execution; supersedes the conjectured [Judge] above):

1. The summary gives a median-runtime table (3 seeds per size) plus a log–log plot covering the full grid n ∈ {200,500,1000,2000} for both methods: Brandes 0.042 / 0.299 / 1.397 / 6.766 s and Naive 0.142 / 2.087 / 15.41 / 121.2 s (with m ≈ 4.0n, i.e. m = Θ(n)). (confirms original [Judge] point 1)
2. Brandes scales near-linearly in nm — fitted slope vs n = 2.21 (≈ n²) and 1.10 vs nm — while the naive baseline is markedly steeper at slope vs n = 2.90 (≈ n³) and 1.45 vs nm; the two slopes are clearly different. (confirms original [Judge] point 2)
3. The speedup grows with n: ~11× at n=1000 (Brandes 1.397 s vs naive 15.41 s) and ~18× at n=2000 (Brandes 6.766 s vs naive 121 s, already at the ~2-min feasibility wall), with Brandes remaining seconds-level — confirming the practical value of O(nm). (confirms original [Judge] point 3)
