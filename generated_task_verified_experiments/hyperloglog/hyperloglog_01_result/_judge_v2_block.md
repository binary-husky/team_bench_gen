Look at `./summary_hll_01_se_scaling.md` — REAL verdict (measured by execution; supersedes the conjectured [Judge] above):

1. Claim (i) judged **FALSE**: doubling `m` gives `SE(2m)/SE(m) = 1/√2 ≈ 0.7071`, i.e. a drop of only `1 − 0.7071 = 29.3%`, not a halving; the correct version states halving needs `m × 4`, since `SE(4m)/SE(m) = 1/2`. (confirms original [Judge] point 1, claim (i))
2. Claim (ii) judged **TRUE**: solving `c/√m' = (1/2)·c/√m` yields `√m' = 2√m ⟹ m' = 4m`, and because memory `B ∝ m`, `B' = 4B` — halving the standard error costs exactly 4× the memory. (confirms original [Judge] point 1, claim (ii))
3. Claim (iii) judged **TRUE**: with `m = 2^p`, `SE(p) = c·2^{−p/2}`, so `SE(p+1)/SE(p) = 2^{−1/2} = 1/√2 ≈ 0.7071`, a drop of ≈ `29.3%` per unit increase in `p`; the summary states halving SE ⟺ `m × 4` ⟺ memory `× 4` ⟺ `p + 2`. (confirms original [Judge] point 1, claim (iii) and the summary)
