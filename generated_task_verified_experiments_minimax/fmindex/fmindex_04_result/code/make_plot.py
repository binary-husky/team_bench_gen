"""Plot index/text size ratio vs text compressibility from results.json."""
import json
import math
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.chdir(os.path.dirname(os.path.abspath(__file__)))

with open("results.json") as f:
    results = json.load(f)

# Sort by text compressibility (gzip(T) size, lower = more compressible)
results.sort(key=lambda r: r["text_gzip_bits"])

names = [r["name"] for r in results]
h0_text = [r["text_h0"] for r in results]
gzip_text_kb = [r["text_gzip_bits"] / 8 / 1024 for r in results]
gzip_bwt_kb = [r["bwt_gzip_bits"] / 8 / 1024 for r in results]
mtf_bwt_kb = [r["mtf_gzip_bits"] / 8 / 1024 for r in results]
fm_index_kb = [r["fm_index_bits"] / 8 / 1024 for r in results]
ratio_uc = [r["ratio_to_uncoded"] for r in results]
ratio_raw = [r["ratio_to_raw"] for r in results]
bps_text_h0 = [r["bps_text_h0"] for r in results]
bps_rle = [r["bps_body_rle"] for r in results]
bps_gzip_mtf = [r["bps_body_gzip_mtf"] for r in results]
runs = [r["bwt_runs"] for r in results]

# --- Figure 1: bits/symbol vs gzip(T) (compressibility axis) ---
fig, ax = plt.subplots(1, 2, figsize=(13, 5.5))

ax[0].plot(gzip_text_kb, bps_text_h0, "o-", label="text H_0")
ax[0].plot(gzip_text_kb, bps_rle, "s-", label="BWT run-RLE body (bps)")
ax[0].plot(gzip_text_kb, bps_gzip_mtf, "^-", label="gzip(MTF(BWT)) (bps)")
ax[0].set_xlabel("gzip(T) size in KB  (← more compressible | less →)")
ax[0].set_ylabel("bits per input symbol")
ax[0].set_title("Information rate vs text compressibility\n(N = 2^20 bytes)")
ax[0].set_yscale("log")
ax[0].grid(True, which="both", alpha=0.3)
ax[0].legend()

# Annotate each point
for x, y, n in zip(gzip_text_kb, bps_rle, names):
    ax[0].annotate(n, (x, y), xytext=(5, 5), textcoords="offset points",
                   fontsize=8, alpha=0.7)

# --- Figure 2: index/text ratio vs gzip(T) ---
ax[1].plot(gzip_text_kb, ratio_uc, "o-", label="FM-index / |T|_uncoded")
ax[1].plot(gzip_text_kb, ratio_raw, "s-", label="FM-index / |T|_raw")
ax[1].axhline(1.0, color="grey", linestyle="--", alpha=0.5, label="size of raw text")
ax[1].set_xlabel("gzip(T) size in KB  (← more compressible | less →)")
ax[1].set_ylabel("FM-index volume / text volume (ratio)")
ax[1].set_title("Index/text ratio vs text compressibility\n(N = 2^20 bytes)")
ax[1].set_yscale("log")
ax[1].grid(True, which="both", alpha=0.3)
ax[1].legend()

for x, y, n in zip(gzip_text_kb, ratio_uc, names):
    ax[1].annotate(n, (x, y), xytext=(5, 5), textcoords="offset points",
                   fontsize=8, alpha=0.7)

plt.tight_layout()
plt.savefig("plot_index_size.png", dpi=130)
print("Saved plot_index_size.png")

# --- Figure 3 (auxiliary): # BWT runs vs gzip(T) ---
fig2, ax2 = plt.subplots(figsize=(7, 5))
ax2.plot(gzip_text_kb, runs, "o-", color="C2")
ax2.set_xlabel("gzip(T) size in KB")
ax2.set_ylabel("Number of BWT runs r")
ax2.set_title("BWT runs vs text compressibility\n(lower r ⇒ more compressible BWT)")
ax2.set_yscale("log")
ax2.grid(True, which="both", alpha=0.3)
for x, y, n in zip(gzip_text_kb, runs, names):
    ax2.annotate(n, (x, y), xytext=(5, 5), textcoords="offset points",
                 fontsize=8, alpha=0.7)
plt.tight_layout()
plt.savefig("plot_bwt_runs.png", dpi=130)
print("Saved plot_bwt_runs.png")