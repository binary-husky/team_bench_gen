"""Plot MAE vs Δf for the sweep, on a log–log scale, together with the
theoretical line MAE = Δf/ε. Also overlay the three query examples from the
main experiment."""

import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = Path(__file__).parent
sweep = json.loads((here / "sensitivity_curve.json").read_text())
main  = json.loads((here / "sensitivity_results.json").read_text())

eps   = sweep["settings"]["epsilon"]
delta = np.array([r["delta_f"]       for r in sweep["records"]])
mae   = np.array([r["empirical_mae"] for r in sweep["records"]])

fig, ax = plt.subplots(figsize=(7, 5))
ax.loglog(delta, mae, "o-",  label="empirical MAE (sweep)")
# theory line
ax.loglog(delta, delta / eps, "k--", lw=1, label=r"theory: MAE = $\Delta f/\varepsilon$")

# three query examples
q_delta = [r["sensitivity"]   for r in main["results"]]
q_mae   = [r["empirical_mae"] for r in main["results"]]
labels  = [r["name"] for r in main["results"]]
ax.loglog(q_delta, q_mae, "s", ms=10, label="three example queries")

ax.set_xlabel(r"query sensitivity  $\Delta f$")
ax.set_ylabel(r"mean absolute error  $\mathrm{MAE}$")
ax.set_title(f"Laplace mechanism: error vs sensitivity  (ε = {eps}, n = {main['settings']['n']}, trials = {main['settings']['trials']})")
ax.grid(True, which="both", ls=":", alpha=0.6)
ax.legend(loc="upper left")

out = here / "sensitivity_plot.png"
fig.tight_layout()
fig.savefig(out, dpi=120)
print("Saved plot to", out)
