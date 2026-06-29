"""
Compare FM-index counting / locating vs. naive substring search on a fixed text.

Fixed:
  - text  (generated once, ~150KB, fixed seed)
  - pattern set (generated once, fixed seed; mix of random and text-derived)
  - implementation
  - self-suffix sentinel (a unique char lex-smaller than all others)

The only varying axis is the search method:
   (a) FM-index backward search (count)            -- O(p) per query
   (b) FM-index locate via LF-walk                 -- O(p * occ) per query
   (c) Naive O(n*m) substring search               -- O(n*m) per query
"""

import time
import random
import json

# ------------------------------------------------------------------
# 1.  Build a fixed text
# ------------------------------------------------------------------
TEXT_SEED = 12345
N_CHARS = 150_000  # ~150 KB
ALPHABET = "abcdefghijklmnopqrstuvwxyz "  # 27 symbols

rng = random.Random(TEXT_SEED)
weights = [4, 1, 3, 4, 13, 2, 2, 6, 7, 1, 1, 4, 3, 7, 8, 2, 1, 6, 6, 9, 3, 1, 2, 1, 2, 1, 18]
assert len(weights) == len(ALPHABET)
text = "".join(rng.choices(ALPHABET, weights=weights, k=N_CHARS))

# Sentinel that is lex-smaller than every symbol in ALPHABET.
SENTINEL = "\x01"
ALPHABET_FULL = SENTINEL + ALPHABET  # '\x01' < ' ' < 'a' < 'b' < ...

# ------------------------------------------------------------------
# 2.  Build the FM-index
# ------------------------------------------------------------------
T = text + SENTINEL
n = len(T)

# Suffix array, 0-indexed internally
sa0 = sorted(range(n), key=lambda i: T[i:])

# BWT[1..n]: BWT[i] = T[SA[i-1] - 1] with wraparound (1-indexed rows)
bwt = [""] * (n + 1)
for i, sa_val in enumerate(sa0):
    bwt[i + 1] = T[(sa_val - 1) % n]

# C[c] in 1-indexed form
full_counts = {ch: 0 for ch in ALPHABET_FULL}
for ch in T:
    full_counts[ch] += 1

C = {}
running = 1
for ch in sorted(ALPHABET_FULL):
    C[ch] = running
    running += full_counts[ch]

# Occ[c][k] = #c in BWT[1..k]  for k = 0..n
distinct = sorted(set(bwt[1:]))
Occ = {ch: [0] * (n + 1) for ch in distinct}
for k in range(1, n + 1):
    ch = bwt[k]
    for c in distinct:
        Occ[c][k] = Occ[c][k - 1]
    Occ[ch][k] += 1


def occ(ch, lo, hi):
    """#ch in BWT[lo..hi] (1-indexed inclusive)."""
    if ch not in Occ:
        return 0
    return Occ[ch][hi] - Occ[ch][lo - 1]


# ------------------------------------------------------------------
# 3.  Backward search -- COUNT
# ------------------------------------------------------------------
def fm_count(pattern):
    if not pattern:
        return 1, 0
    c = pattern[-1]
    if c not in C:
        return 1, 0
    sp = C[c]
    ep = sp + occ(c, 1, n) - 1
    i = len(pattern) - 2
    while sp <= ep and i >= 0:
        c = pattern[i]
        if c not in C:
            return 1, 0
        sp = C[c] + occ(c, 1, sp - 1)
        ep = C[c] + occ(c, 1, ep) - 1
        i -= 1
    if sp > ep:
        return 1, 0
    return sp, ep


# ------------------------------------------------------------------
# 4.  LF-walk -- LOCATE positions
# ------------------------------------------------------------------
def fm_locate(pattern):
    sp, ep = fm_count(pattern)
    if sp > ep:
        return []
    positions = []
    for s in range(sp, ep + 1):
        pos = s
        steps = 0
        while bwt[pos] != SENTINEL:
            ch = bwt[pos]
            pos = C[ch] + occ(ch, 1, pos) - 1
            steps += 1
        positions.append(steps)
    return positions


# ------------------------------------------------------------------
# 5.  Naive O(n*m) search
# ------------------------------------------------------------------
def naive_search(pattern):
    out = []
    if not pattern:
        return out
    n_body = len(text)
    m = len(pattern)
    for i in range(n_body - m + 1):
        if text[i:i + m] == pattern:
            out.append(i)
    return out


# ------------------------------------------------------------------
# 6.  Generate pattern set (FIXED seed)
# ------------------------------------------------------------------
PAT_SEED = 54321
N_PATTERNS_RAND = 100
PATTERN_LENS = [3, 5, 8, 12, 20]

# (a) Random patterns
prng = random.Random(PAT_SEED)
rand_patterns = []
for _ in range(N_PATTERNS_RAND):
    L = prng.choice(PATTERN_LENS)
    s = "".join(prng.choice(ALPHABET) for _ in range(L))
    rand_patterns.append(s)

# (b) Patterns extracted from the text itself (guaranteed to occur, often
#     many times for short lengths).  Same fixed positions per length.
prng2 = random.Random(PAT_SEED + 1)
text_patterns = []
for L in PATTERN_LENS:
    for _ in range(20):  # 20 per length = 100 total
        start = prng2.randint(0, len(text) - L)
        text_patterns.append(text[start:start + L])

# Final pattern set: union
patterns = rand_patterns + text_patterns
N_PATTERNS = len(patterns)


# ------------------------------------------------------------------
# 7.  Verify correctness
# ------------------------------------------------------------------
ok_count = ok_locate = True
for p in patterns:
    a = fm_count(p)
    expected = len(naive_search(p))
    got_count = max(0, a[1] - a[0] + 1)
    if got_count != expected:
        ok_count = False
        print(f"COUNT MISMATCH for {p!r}: fm={got_count}, naive={expected}")
    locs = fm_locate(p)
    if sorted(locs) != sorted(naive_search(p)):
        ok_locate = False
        if len(locs) < 6:
            print(f"LOCATE MISMATCH for {p!r}: fm={sorted(locs)}, naive={sorted(naive_search(p))}")

print(f"Correctness on all {len(patterns)} patterns: count OK = {ok_count}, locate OK = {ok_locate}")


# ------------------------------------------------------------------
# 8.  Timing
# ------------------------------------------------------------------
def time_block(fn, args_list):
    per = []
    # warm up
    for a in args_list[:3]:
        fn(a)
    t0 = time.perf_counter()
    for a in args_list:
        t1 = time.perf_counter()
        fn(a)
        t2 = time.perf_counter()
        per.append(t2 - t1)
    t_end = time.perf_counter()
    return t_end - t0, per


t_count, per_count = time_block(fm_count, patterns)
t_locate, per_locate = time_block(fm_locate, patterns)
t_naive, per_naive = time_block(naive_search, patterns)


# ------------------------------------------------------------------
# 9.  Aggregate stats
# ------------------------------------------------------------------
def stats(xs):
    xs_sorted = sorted(xs)
    return {
        "n": len(xs_sorted),
        "total_s": sum(xs),
        "mean_s": sum(xs) / len(xs),
        "median_s": xs_sorted[len(xs_sorted) // 2],
        "min_s": xs_sorted[0],
        "max_s": xs_sorted[-1],
    }


s_count = stats(per_count)
s_locate = stats(per_locate)
s_naive = stats(per_naive)


# ------------------------------------------------------------------
# 10. Per-pattern length breakdown (over the whole pattern set)
# ------------------------------------------------------------------
by_len = {L: {"count": [], "locate": [], "naive": [], "occ": []} for L in PATTERN_LENS}
for p, c_t, l_t, n_t in zip(patterns, per_count, per_locate, per_naive):
    L = len(p)
    sp, ep = fm_count(p)
    occ_count = max(0, ep - sp + 1)
    by_len[L]["count"].append(c_t)
    by_len[L]["locate"].append(l_t)
    by_len[L]["naive"].append(n_t)
    by_len[L]["occ"].append(occ_count)

# Also: per-pattern length breakdown restricted to text-derived patterns
# (so occ > 0 typically).
text_by_len = {L: {"count": [], "locate": [], "naive": [], "occ": []} for L in PATTERN_LENS}
for p, c_t, l_t, n_t in zip(text_patterns, per_count[-len(text_patterns):],
                            per_locate[-len(text_patterns):],
                            per_naive[-len(text_patterns):]):
    L = len(p)
    sp, ep = fm_count(p)
    occ_count = max(0, ep - sp + 1)
    text_by_len[L]["count"].append(c_t)
    text_by_len[L]["locate"].append(l_t)
    text_by_len[L]["naive"].append(n_t)
    text_by_len[L]["occ"].append(occ_count)


# ------------------------------------------------------------------
# 11. Print
# ------------------------------------------------------------------
print()
print("=" * 90)
print(f"Text length (incl. sentinel)   : {n}  ({n-1} body + 1 sentinel)")
print(f"Distinct BWT symbols           : {len(distinct)}")
print(f"#patterns (total)              : {len(patterns)}  "
      f"({len(rand_patterns)} random + {len(text_patterns)} text-derived)")
print("=" * 90)
print(f"{'Method':<25}{'total (s)':>12}{'mean (s)':>14}{'median (s)':>14}{'min (s)':>14}{'max (s)':>14}")
for name, s in [("FM-index count", s_count),
                ("FM-index locate", s_locate),
                ("Naive O(n*m)", s_naive)]:
    print(f"{name:<25}{s['total_s']:>12.6f}{s['mean_s']:>14.9f}{s['median_s']:>14.9f}"
          f"{s['min_s']:>14.9f}{s['max_s']:>14.9f}")
print()
print("Per-pattern-length over ALL patterns (mean time in seconds, mean #occ):")
print(f"{'L':>5}{'#pats':>8}{'count(s)':>14}{'locate(s)':>14}{'naive(s)':>14}{'occ':>10}")
for L in PATTERN_LENS:
    d = by_len[L]
    n_ = len(d["count"])
    if n_ == 0:
        continue
    print(f"{L:>5}{n_:>8}"
          f"{sum(d['count'])/n_:>14.9f}"
          f"{sum(d['locate'])/n_:>14.9f}"
          f"{sum(d['naive'])/n_:>14.9f}"
          f"{sum(d['occ'])/n_:>10.2f}")
print()
print("Per-pattern-length over TEXT-DERIVED patterns (always present, mean #occ > 0):")
print(f"{'L':>5}{'#pats':>8}{'count(s)':>14}{'locate(s)':>14}{'naive(s)':>14}{'occ':>10}")
for L in PATTERN_LENS:
    d = text_by_len[L]
    n_ = len(d["count"])
    if n_ == 0:
        continue
    print(f"{L:>5}{n_:>8}"
          f"{sum(d['count'])/n_:>14.9f}"
          f"{sum(d['locate'])/n_:>14.9f}"
          f"{sum(d['naive'])/n_:>14.9f}"
          f"{sum(d['occ'])/n_:>10.2f}")


# ------------------------------------------------------------------
# 12. Save raw results for the summary
# ------------------------------------------------------------------
result = {
    "n_text_incl_sentinel": n,
    "n_text_body": n - 1,
    "n_patterns_total": len(patterns),
    "n_patterns_random": len(rand_patterns),
    "n_patterns_text": len(text_patterns),
    "pattern_lens": PATTERN_LENS,
    "ok_count": ok_count,
    "ok_locate": ok_locate,
    "stats_all": {
        "count": s_count,
        "locate": s_locate,
        "naive": s_naive,
    },
    "by_len_all": {
        L: {
            "n": len(d["count"]),
            "mean_count_s": sum(d["count"]) / len(d["count"]),
            "mean_locate_s": sum(d["locate"]) / len(d["locate"]),
            "mean_naive_s": sum(d["naive"]) / len(d["naive"]),
            "mean_occ": sum(d["occ"]) / len(d["occ"]),
        } for L, d in by_len.items() if d["count"]
    },
    "by_len_text": {
        L: {
            "n": len(d["count"]),
            "mean_count_s": sum(d["count"]) / len(d["count"]),
            "mean_locate_s": sum(d["locate"]) / len(d["locate"]),
            "mean_naive_s": sum(d["naive"]) / len(d["naive"]),
            "mean_occ": sum(d["occ"]) / len(d["occ"]),
        } for L, d in text_by_len.items() if d["count"]
    },
}
with open("raw_results.json", "w") as f:
    json.dump(result, f, indent=2)
print("\nWrote raw_results.json")
