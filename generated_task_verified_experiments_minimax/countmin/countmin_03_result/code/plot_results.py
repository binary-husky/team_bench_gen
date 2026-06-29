"""Make a log-scale plot of empirical tail-failure rate vs theory (1/e)^d."""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Empirical results from raw_rates.csv
data = np.genfromtxt("raw_rates.csv", delimiter=",", skip_header=1)
d = data[:, 0]
emp_mean = data[:, 1]
emp_std = data[:, 2]

theory = (1.0 / np.e) ** d

fig, ax = plt.subplots(figsize=(7, 4.5))
ax.errorbar(d, emp_mean, yerr=emp_std, marker="o", lw=2, capsize=4,
            label="empirical (this experiment)")
ax.plot(d, theory, marker="s", lw=2, ls="--",
        label=r"theory upper bound $(1/e)^d = e^{-d}$")

# Add a faint y-floor line at 1 / (25 * 1e5) ≈ 4e-7 for context
floor = 1.0 / (25 * 100_000)
ax.axhline(floor, color="grey", ls=":", lw=1,
           label=f"detection floor  1/(seeds·items) ≈ {floor:.0e}")

ax.set_yscale("log")
ax.set_xlabel("depth $d$")
ax.set_ylabel("tail-failure rate  Pr[$\\hat a_i > a_i + T$]")
ax.set_title("Count-Min: tail-failure vs depth (w = 1024, Zipfian s = 1.0)")
ax.set_xticks(d)
ax.grid(True, which="both", ls=":", alpha=0.5)
ax.legend(loc="lower left")
fig.tight_layout()
fig.savefig("tail_vs_depth.png", dpi=140)
print("wrote tail_vs_depth.png")