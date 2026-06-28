Look at `./summary_betweenness_04_sampling.md` — REAL verdict (measured by execution; supersedes the conjectured [Judge] above):

1. §2 gives a full table over K ∈ {10, 50, 100, 500, 2000} plus exact (k=None), reporting per-K max|误差| (mean±std), RMSE, L1 error, Spearman, Top-20 overlap, runtime (mean±std), and speedup vs exact — all from **7 seeds** (≥5); exact (k=None) runtime **10.47 s**. (confirms original [Judge] point 1)

2. Error decreases with K and follows the ≈1/√K law in the sampling region: log-log slope of max|误差| vs K = **−0.525** (theory −0.50, R²=**0.994**) and RMSE slope **−0.506** (R²=**0.997**); error·√K is near-constant (K=10→0.298, 50→0.320, 100→0.289, 500→0.274); K×5 ratio checks give ÷2.08 (10→50) and ÷2.36 (100→500) vs predicted ÷2.24. K=2000 drops faster (÷4.3 vs ÷2.0) because it enters the saturation region (K/n=67%). (confirms original [Judge] point 2)

3. Speedup is significant at small K — K=10→**295×**, 50→**60×**, 100→**30×**, 500→**5.9×**, 2000→**1.5×** (≈n/K); the summary recommends compromise **K=500**: max|误差|≈**1.2%**, Top-20 overlap **0.95**, Spearman **0.93**, runtime **1.76 s vs 10.47 s** (~6× faster). (confirms original [Judge] point 3)
