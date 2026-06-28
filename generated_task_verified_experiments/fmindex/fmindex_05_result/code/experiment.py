"""
FM-index (count/locate) vs naive O(n*m) substring search — speed comparison.

Reference: Ferragina & Manzini, "Opportunistic Data Structures with Applications"
(2000) — the FM-index paper in ./fmindex_material/.

Implements from scratch (CPU only):
  * Burrows-Wheeler Transform via a prefix-doubling suffix array.
  * C[] array (cumulative char counts) and a full Occ(c, i) rank table.
  * Backward-search COUNT (O(p) with full Occ table).
  * LF-walking LOCATE with sampled SA (O(occ * d) with sampling step d).
  * Naive O(n*m) substring scan (pure Python, char-by-char, early exit).

Fixed setup: text, pattern set, random seed, implementation. Independent
variable = query method (count / locate / naive).
"""

import time
import numpy as np

SEED = 12345
TEXT_LEN = 150_000          # ~150 KB (within 100-200 KB)
ALPHABET = "ACGT"           # 4-letter DNA alphabet -> random patterns hit
SENTINEL = "$"              # lex-smallest, unique, makes all suffixes distinct
SAMPLE_D = 4                # SA sampling step for LF-walk locate

# ---- char <-> code mapping (sentinel is code 0, lex-smallest) ----
CHARS = [SENTINEL] + list(ALPHABET)
CODE = {c: i for i, c in enumerate(CHARS)}   # '$'->0,'A'->1,'C'->2,'G'->3,'T'->4
SIGMA = len(CHARS)


def gen_text(seed):
    rng = np.random.default_rng(seed)
    codes = rng.integers(1, SIGMA, size=TEXT_LEN)  # 1..4 -> ACGT, no sentinel
    return "".join(CHARS[c] for c in codes)


def gen_patterns(text, seed, n=30, lo=6, hi=10):
    """Random patterns; also record how many actually occur (some may be absent)."""
    rng = np.random.default_rng(seed + 1)
    pats = []
    for _ in range(n):
        m = int(rng.integers(lo, hi + 1))
        start = int(rng.integers(0, len(text) - m))
        pats.append(text[start:start + m])  # guaranteed to occur at least once
    # mix in a few that may be absent (fully random)
    for _ in range(10):
        m = int(rng.integers(12, 16))   # longer -> rarer, likely 0-1 hits
        pats.append("".join(CHARS[int(c)] for c in rng.integers(1, SIGMA, size=m)))
    return pats


# ---------------------------------------------------------------- suffix array
def suffix_array(s_codes):
    """Prefix-doubling suffix array. s_codes: np.int64 array incl. sentinel=0."""
    n = len(s_codes)
    sa = np.arange(n, dtype=np.int64)
    rank = s_codes.astype(np.int64).copy()
    k = 1
    while True:
        second = np.full(n, -1, dtype=np.int64)
        nk = n - k
        if nk > 0:
            second[:nk] = rank[k:n]
        key = rank * (n + 2) + (second + 1)
        sa = np.argsort(key, kind="stable")
        sorted_keys = key[sa]
        newrank = np.empty(n, dtype=np.int64)
        newrank[sa[0]] = 0
        neq = sorted_keys[1:] != sorted_keys[:-1]
        newrank[sa[1:]] = np.cumsum(neq)
        rank = newrank
        if rank[sa[-1]] == n - 1:        # all distinct -> done
            break
        k *= 2
    return sa


# ----------------------------------------------------------------- FM-index build
class FMIndex:
    def __init__(self, text):
        # append sentinel (code 0)
        codes = np.array([CODE[c] for c in text] + [0], dtype=np.int64)
        n = len(codes)
        self.n = n
        self.text = text

        t0 = time.perf_counter()
        sa = suffix_array(codes)
        self.build_sa_time = time.perf_counter() - t0

        t0 = time.perf_counter()
        # BWT[i] = codes[(sa[i]-1) % n]
        bwt = codes[(sa - 1) % n]
        self.bwt = bwt

        # C[c] = number of chars in T' strictly less than c
        counts = np.bincount(codes, minlength=SIGMA)
        C = np.zeros(SIGMA, dtype=np.int64)
        C[1:] = np.cumsum(counts)[:-1]      # C[0]=0 (sentinel is smallest)
        self.C = C

        # full Occ table: occ[c, i] = count of c in bwt[0:i], i in [0,n]
        occ = np.zeros((SIGMA, n + 1), dtype=np.int32)
        for c in range(SIGMA):
            mask = (bwt == c).astype(np.int32)
            occ[c, 1:] = np.cumsum(mask)
        self.occ = occ
        self.bwt_build_time = time.perf_counter() - t0

        # SA sampling for locate: store SA[i] where SA[i] % SAMPLE_D == 0
        self.sa_sampled = np.full(n, -1, dtype=np.int64)
        sampled_mask = (sa % SAMPLE_D == 0)
        self.sa_sampled[sampled_mask] = sa[sampled_mask]

    # backward-search count: returns (sp, ep); count = ep - sp
    def count(self, pattern):
        sp, ep = 0, self.n
        for ch in reversed(pattern):
            c = CODE.get(ch, -1)
            if c < 0:
                return 0, 0
            sp = int(self.C[c] + self.occ[c, sp])
            ep = int(self.C[c] + self.occ[c, ep])
            if sp >= ep:
                return 0, 0
        return int(sp), int(ep)

    # LF mapping: row i -> row of the char preceding position SA[i]
    def _lf(self, i):
        c = self.bwt[i]
        return int(self.C[c] + self.occ[c, i])

    # locate all occurrences via LF walk (returns sorted positions in text)
    def locate(self, pattern):
        sp, ep = self.count(pattern)
        if sp == ep:
            return []
        out = []
        for r in range(sp, ep):
            steps = 0
            cur = r
            while self.sa_sampled[cur] < 0:
                cur = self._lf(cur)
                steps += 1
            pos = int(self.sa_sampled[cur] + steps) % self.n
            out.append(pos)
        return sorted(out)


# ----------------------------------------------------------------- naive search
def naive_search(text, pattern):
    """Honest O(n*m) scan: char-by-char with early exit, pure Python."""
    n = len(text)
    m = len(pattern)
    if m == 0 or m > n:
        return []
    res = []
    limit = n - m + 1
    for i in range(limit):
        j = 0
        while j < m and text[i + j] == pattern[j]:
            j += 1
        if j == m:
            res.append(i)
    return res


# --------------------------------------------------------------------- driver
def main():
    text = gen_text(SEED)
    patterns = gen_patterns(text, SEED)
    print(f"text length: {len(text)} bytes")
    print(f"#patterns: {len(patterns)}")

    t0 = time.perf_counter()
    fm = FMIndex(text)
    print(f"SA build:        {fm.build_sa_time*1000:8.2f} ms")
    print(f"BWT+Occ build:   {fm.bwt_build_time*1000:8.2f} ms")
    print(f"Occ table shape: {fm.occ.shape}  (~{fm.occ.nbytes/1e6:.2f} MB)")
    print(f"SA samples:      {int((fm.sa_sampled>=0).sum())}")

    # ---- correctness check vs naive (small subset) ----
    mismatches = 0
    for p in patterns:
        c_cnt = fm.count(p)[1] - fm.count(p)[0]
        n_pos = naive_search(text, p)
        loc = fm.locate(p)
        if c_cnt != len(n_pos) or loc != n_pos:
            mismatches += 1
    print(f"correctness mismatches: {mismatches} / {len(patterns)}")
    assert mismatches == 0, "FM-index disagrees with naive search!"

    # ---- timing ----
    COUNT_REPS = 500
    LOCATE_REPS = 100
    NAIVE_REPS = 1

    rows = []
    tot_count = tot_locate = tot_naive = 0.0
    for p in patterns:
        # warm up
        for _ in range(3):
            fm.count(p); fm.locate(p)

        t0 = time.perf_counter()
        for _ in range(COUNT_REPS):
            sp, ep = fm.count(p)
        ct = (time.perf_counter() - t0) / COUNT_REPS

        t0 = time.perf_counter()
        for _ in range(LOCATE_REPS):
            loc = fm.locate(p)
        lt = (time.perf_counter() - t0) / LOCATE_REPS

        t0 = time.perf_counter()
        for _ in range(NAIVE_REPS):
            npos = naive_search(text, p)
        nt = (time.perf_counter() - t0) / NAIVE_REPS

        occ = ep - sp
        rows.append((p, len(p), occ, ct, lt, nt))
        tot_count += ct; tot_locate += lt; tot_naive += nt

    # ---- write summary ----
    with open("summary_speed_vs_naive.md", "w") as f:
        f.write("# FM-index (count / locate) vs naive O(n·m) substring search\n\n")
        f.write("Speed comparison on a fixed text with a fixed pattern set.\n\n")
        f.write("## Setup (fixed)\n\n")
        f.write(f"- **Text**: {len(text)} bytes, alphabet `ACGT`, generated with "
                f"`numpy.random.default_rng({SEED})` (CPU, fixed seed).\n")
        f.write(f"- **Sentinel**: `'{SENTINEL}'` appended (lex-smallest, unique) so all "
                f"suffixes are distinct.\n")
        f.write(f"- **Patterns**: {len(patterns)} random patterns of length 6–15 "
                f"(first 30 seeded from the text so they occur at least once; last 10 "
                f"fully random, rarer — some absent).\n")
        f.write(f"- **FM-index**: BWT via prefix-doubling suffix array; full `Occ(c,i)` "
                f"rank table of shape `{tuple(fm.occ.shape)}` "
                f"(~{fm.occ.nbytes/1e6:.1f} MB); SA sampled every `{SAMPLE_D}` rows "
                f"for LF-walk locate.\n")
        f.write(f"- **Naive**: pure-Python O(n·m) scan, char-by-char, early exit.\n")
        f.write(f"- **Correctness**: FM-index count and locate positions matched the "
                f"naive search for **all {len(patterns)} patterns** (0 mismatches).\n\n")
        f.write("Independent variable = query method (count / locate / naive); "
                "everything else fixed.\n\n")

        f.write("## Build cost (one-time, not per query)\n\n")
        f.write(f"| step | time |\n|---|---|\n")
        f.write(f"| suffix array (prefix doubling) | {fm.build_sa_time*1000:.1f} ms |\n")
        f.write(f"| BWT + C + full Occ table | {fm.bwt_build_time*1000:.1f} ms |\n")
        f.write(f"| total build | {(fm.build_sa_time+fm.bwt_build_time)*1000:.1f} ms |\n\n")

        f.write("## Per-query results\n\n")
        f.write("Times averaged over many reps for the fast FM-index paths "
                f"(count ×{COUNT_REPS}, locate ×{LOCATE_REPS}); naive ×{NAIVE_REPS} "
                f"(it is slow). All times in **microseconds (µs)**.\n\n")
        f.write("| # | pattern | m | occ | count µs | locate µs | naive µs | "
                "count/naive | locate/naive |\n")
        f.write("|---|---|--:|--:|--:|--:|--:|--:|--:|\n")
        for i, (p, m, occ, ct, lt, nt) in enumerate(rows):
            cr = ct / nt if nt > 0 else float("inf")
            lr = lt / nt if nt > 0 else float("inf")
            f.write(f"| {i+1} | `{p}` | {m} | {occ} | {ct*1e6:.2f} | "
                    f"{lt*1e6:.2f} | {nt*1e6:.1f} | {cr:.4f} | {lr:.4f} |\n")

        f.write("\n## Totals across all %d queries (single-query avg × N)\n\n" % len(rows))
        f.write("| method | total time | \n|---|---|\n")
        f.write(f"| FM-index count | {tot_count*1e6:.1f} µs "
                f"({tot_count*1e3:.3f} ms) |\n")
        f.write(f"| FM-index locate | {tot_locate*1e6:.1f} µs "
                f"({tot_locate*1e3:.3f} ms) |\n")
        f.write(f"| naive O(n·m) | {tot_naive*1e6:.1f} µs "
                f"({tot_naive*1e3:.3f} ms) |\n\n")

        f.write("## Conclusion\n\n")
        sc = tot_naive / tot_count if tot_count > 0 else float("inf")
        sl = tot_naive / tot_locate if tot_locate > 0 else float("inf")
        f.write(f"- **Count**: FM-index backward-search count is **{sc:.0f}×** faster "
                f"than naive scanning in total ({tot_count*1e3:.3f} ms vs "
                f"{tot_naive*1e3:.3f} ms over {len(rows)} queries). Count cost is "
                f"essentially independent of text length — `O(p)` with the full Occ "
                f"table, vs naive `O(n·m)`.\n")
        f.write(f"- **Locate**: FM-index LF-walk locate is **{sl:.0f}×** faster than "
                f"naive in total ({tot_locate*1e3:.3f} ms vs {tot_naive*1e3:.3f} ms). "
                f"Locate cost grows with `occ` (`O(occ·d)` for sampling step "
                f"d={SAMPLE_D}); for the low-occurrence patterns here it stays far "
                f"below naive, and would only approach/beaten-by naive when a pattern "
                f"occurs very frequently (occ ≈ Θ(n)).\n")
        f.write(f"- **Per-query pattern**: longer / rarer patterns (small `occ`) make "
                f"FM-index's advantage largest, since naive always pays `O(n·m)` while "
                f"count pays `O(p)` and locate pays `O(occ·d)`.\n")
        f.write(f"- **Trade-off**: the speedup is bought with a one-time build cost of "
                f"~{(fm.build_sa_time+fm.bwt_build_time)*1000:.0f} ms and "
                f"~{fm.occ.nbytes/1e6:.1f} MB of index memory; for a *single* ad-hoc "
                f"query naive wins, but for a *batch* of queries over the same text the "
                f"FM-index amortises its build cost and dominates.\n")

    print("\n--- totals ---")
    print(f"count total : {tot_count*1e6:.1f} µs")
    print(f"locate total: {tot_locate*1e6:.1f} µs")
    print(f"naive total : {tot_naive*1e6:.1f} µs")
    print(f"count speedup : {tot_naive/tot_count:.1f}x")
    print(f"locate speedup: {tot_naive/tot_locate:.1f}x")
    print("wrote summary_speed_vs_naive.md")


if __name__ == "__main__":
    main()
