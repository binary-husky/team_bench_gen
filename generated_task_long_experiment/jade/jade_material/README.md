# Research Materials — JADE (Adaptive Differential Evolution with Optional External Archive)

Materials collected during the JADE reproduction / ablation study.

The big subject is **reproducing JADE** (Zhang & Sanderson, IEEE TEVC 2009) and dissecting its key design choices: the `DE/current-to-pbest` mutation, the optional external archive of inferior solutions, the Cauchy/Gaussian parameter adaptation with Lehmer vs arithmetic means, and the two insensitive control parameters `c` and `p`.

## Index

| File | Source | What it is |
|------|--------|-----------|
| `jade_paper_original.pdf` | IEEE Xplore (DOI 10.1109/TEVC.2008.926030 / doc 5208221) | The original paper: *JADE: Adaptive Differential Evolution with Optional External Archive*, Zhang & Sanderson, IEEE TEVC 13(5), Oct 2009 |
| `turboJADE_README.md` | https://github.com/hippke/turboJADE/blob/main/README.md | README of `turboJADE`, a pure-Python numba-JIT'd JADE implementation. Cites Zhang & Sanderson (2009), inspired by PyFDE. |
| `turboJADE.py` | https://github.com/hippke/turboJADE/blob/main/turboJADE.py | Reference Python implementation of JADE with archive. Useful as a sanity-check / structural reference for the repro. |
| `pypop7_jade.py` | https://github.com/Evolutionary-Intelligence/pypop/blob/main/pypop7/optimizers/de/jade.py | The pypop7 library's JADE module — a second independent implementation to cross-check the algorithm. |
| `kostyfisik_jade_README.md` | https://github.com/kostyfisik/jade/blob/master/README.md | JADE++ (C++ port) README; describes algorithm options and reference results. |
| `scipy_DE_docs.html` | https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html | scipy's classic DE documentation — used as a reference for the DE/rand/1/bin baseline (jDE / SaDE / classic-DE comparison). |

## Notes

- The PDF is the authoritative source for all algorithm details (eqs. 1–12, Table I pseudocode, Tables IV–VIII numerical results, Figs. 2–5).
- The `DE/current-to-pbest/1` mutation with archive (paper eq. 7) is the JADE-with-archive variant; setting archive size to 0 recovers the no-archive variant (eq. 6).
- Standard parameter setting used throughout the paper's experiments: `c = 0.1` (so 1/c = 10 generations life span), `p = 0.05` (top 5%), `NP ∈ {30, 100, 400}` for `D ∈ {≤10, 30, 100}` respectively, `μF = μCR = 0.5` init.
- The benchmark suite is f1–f13 (Yao/Liu/Lin 1999, 30-D and 100-D scalable) plus the Dixon–Szegö set f14–f20 (2–6-D).
- Two reference implementations (`turboJADE.py`, `pypop7_jade.py`) are included as cross-checks but the repro should follow the paper's Table I pseudocode directly.
