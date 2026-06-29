"""
Extra analysis: per-frequency-bucket error breakdown and a plot,
to make the Zipfian-vs-uniform story crisper.
"""
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import struct
import mmh3
import time

N = 1_000_000
N_ITEMS = 100_000
d = 5
widths = [128, 256, 512, 1024, 2048, 4096]
seeds = [11, 22, 33]

rng = np.random.default_rng(20260528)


def gen_uniform_stream(rng):
    stream = rng.integers(0, N_ITEMS, size=N, dtype=np.int64)
    counts = np.bincount(stream, minlength=N_ITEMS).astype(np.float64)
    return stream, counts


def gen_zipfian_stream(rng, s=1.0):
    ranks = np.arange(1, N_ITEMS + 1, dtype=np.float64)
    p = 1.0 / (ranks ** s)
    p /= p.sum()
    stream = rng.choice(N_ITEMS, size=N, replace=True, p=p).astype(np.int64)
    counts = np.bincount(stream, minlength=N_ITEMS).astype(np.float64)
    return stream, counts


def build_buckets(w, d, seed):
    items = np.arange(N_ITEMS, dtype=np.int64)
    bucket = np.empty((d, N_ITEMS), dtype=np.int64)
    for j in range(d):
        col = np.empty(N_ITEMS, dtype=np.int64)
        salt = (seed * 131 + j) & 0xFFFFFFFF
        for i in range(N_ITEMS):
            col[i] = mmh3.hash128(struct.pack("<q", int(items[i])), seed=salt, signed=False) % w
        bucket[j] = col
    return bucket


def run_one(stream, true_counts, w, d, seed):
    bucket = build_buckets(w, d, seed)
    counts = np.zeros((d, w), dtype=np.int64)
    for j in range(d):
        counts[j] = np.bincount(bucket[j, stream], minlength=w)
    # Per-row lookup: for each row j, gather counts[j] at bucket[j, item] for every item.
    per_row = np.take_along_axis(counts, bucket, axis=1)
    return per_row.min(axis=0).astype(np.float64)


def main():
    t0 = time.time()
    stream_uni, counts_uni = gen_uniform_stream(rng)
    stream_zip, counts_zip = gen_zipfian_stream(rng, s=1.0)

    results = {"uniform": {"w": [], "mean": [], "p99": [], "max": []},
               "zipfian": {"w": [], "mean": [], "p99": [], "max": []}}

    for label, stream, tc in [("uniform", stream_uni, counts_uni),
                              ("zipfian", stream_zip, counts_zip)]:
        for w in widths:
            errs = []
            for s in seeds:
                est = run_one(stream, tc, w, d, s)
                over = np.maximum(est - tc, 0.0)
                errs.append(over)
            stacked = np.stack(errs)  # (n_seeds, N_ITEMS)
            mean_m = stacked.mean(axis=0).mean()  # avg over seeds, then items
            p99_m = np.percentile(stacked.mean(axis=0), 99)
            max_m = stacked.mean(axis=0).max()
            results[label]["w"].append(w)
            results[label]["mean"].append(float(mean_m))
            results[label]["p99"].append(float(p99_m))
            results[label]["max"].append(float(max_m))

    print(json.dumps(results, indent=2))

    # Save full results
    with open("results_full.json", "w") as f:
        json.dump(results, f, indent=2)

    # ---- Plot ----
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    for ax, label in zip(axes, ["uniform", "zipfian"]):
        w = np.array(results[label]["w"])
        mean = np.array(results[label]["mean"])
        p99 = np.array(results[label]["p99"])
        mx = np.array(results[label]["max"])
        ax.plot(w, mean, "o-", label="mean overestimation")
        ax.plot(w, p99, "s-", label="99th-percentile overestimation")
        ax.plot(w, mx, "^-", label="max overestimation", alpha=0.7)
        # 1/w reference scaled to first point
        ref = mean[0] * w[0] / w
        ax.plot(w, ref, "k--", alpha=0.5, label="∝ 1/w reference")
        ax.set_xscale("log", base=2)
        ax.set_yscale("log")
        ax.set_xlabel("width w")
        ax.set_ylabel("overestimation â_i − a_i")
        ax.set_title(f"{label.capitalize()} distribution")
        ax.legend()
        ax.grid(True, which="both", alpha=0.3)

    fig.suptitle(f"Count-Min Sketch overestimation vs width w  (d={d}, N=1e6, n=1e5, 3 seeds)")
    fig.tight_layout()
    fig.savefig("plot_width_vs_error.png", dpi=130)
    print(f"Wrote plot_width_vs_error.png  (total {time.time()-t0:.1f}s)")

    # ---- Heavy-hitter analysis for Zipfian at largest w ----
    # Show that top items in Zipfian have massive errors relative to item count
    w = 4096
    est = run_one(stream_zip, counts_zip, w, d, seeds[0])
    order = np.argsort(-counts_zip)  # heaviest first
    top_idx = order[:10]
    print("\nTop-10 Zipfian items @ w=4096, seed=11:")
    print(f"{'rank':>4} {'true':>10} {'est':>10} {'over':>10} {'over/true':>10}")
    for r, i in enumerate(top_idx, 1):
        e = float(est[int(i)])
        ov = max(e - float(counts_zip[int(i)]), 0.0)
        ratio = ov / max(float(counts_zip[int(i)]), 1.0)
        print(f"{r:>4} {counts_zip[int(i)]:>10.0f} {e:>10.0f} {ov:>10.0f} {ratio:>10.3f}")

    # And uniform @ w=4096
    est_u = run_one(stream_uni, counts_uni, w, d, seeds[0])
    order_u = np.argsort(-counts_uni)
    top_idx_u = order_u[:5]
    print("\nTop-5 Uniform items @ w=4096, seed=11:")
    print(f"{'rank':>4} {'true':>10} {'est':>10} {'over':>10} {'over/true':>10}")
    for r, i in enumerate(top_idx_u, 1):
        e = float(est_u[int(i)])
        ov = max(e - float(counts_uni[int(i)]), 0.0)
        ratio = ov / max(float(counts_uni[int(i)]), 1.0)
        print(f"{r:>4} {counts_uni[int(i)]:>10.0f} {e:>10.0f} {ov:>10.0f} {ratio:>10.3f}")

    # Tail of Zipfian (light items) - mean overestimation there
    light_zip = counts_zip < 10
    light_zip_err = float(np.maximum(est[light_zip] - counts_zip[light_zip], 0.0).mean())
    print(f"\nMean overestimation for Zipfian items with true count < 10: {light_zip_err:.4f}")


if __name__ == "__main__":
    main()