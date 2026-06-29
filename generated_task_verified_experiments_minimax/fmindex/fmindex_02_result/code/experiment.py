"""
Correctness experiment: FM-index backward-search count vs. brute-force count.

Fixed configuration (per task):
  - text       : random DNA, length 200_000, fixed seed 1234
  - patterns   : deterministic set, fixed seed 1234
  - alphabet   : {A, C, G, T}
  - implementation: fmindex.py

We compare BACKWARD SEARCH count (overlapping, like all-occurrences substring
count) vs. an explicit OVERLAPPING brute-force substring counter.
"""

from __future__ import annotations

import random
import time
import json
from collections import Counter

from fmindex import FMIndex


# ---------------------------------------------------------------------------
# Brute-force overlapping count (FM-index also counts overlapping occurrences)
# ---------------------------------------------------------------------------
def brute_force_count_overlap(text: bytes, pattern: bytes) -> int:
    if len(pattern) == 0 or len(pattern) > len(text):
        return 0
    cnt = 0
    n, m = len(text), len(pattern)
    # Use str.find in a loop (still brute-force, but Python-level C-speed).
    start = 0
    while True:
        idx = text.find(pattern, start)
        if idx < 0:
            break
        cnt += 1
        start = idx + 1
    return cnt


# ---------------------------------------------------------------------------
# Build text
# ---------------------------------------------------------------------------
def build_text(seed: int, n: int) -> bytes:
    rng = random.Random(seed)
    alphabet = b"ACGT"
    return bytes(rng.choice(alphabet) for _ in range(n))


# ---------------------------------------------------------------------------
# Build pattern set
# ---------------------------------------------------------------------------
def build_patterns(seed: int, text: bytes) -> list[tuple[str, bytes]]:
    """
    Returns a list of (category, pattern) pairs covering:
      - short present patterns
      - medium present patterns
      - long present patterns
      - patterns with no occurrences
      - single-character patterns (all 4 bases)
      - self-overlapping patterns (e.g. 'AAA')
      - patterns that span the first / last position of the text (boundary)
      - patterns containing every char of the alphabet
      - the empty pattern
    """
    rng = random.Random(seed)
    patterns: list[tuple[str, bytes]] = []

    # 1) Random short patterns (length 1..6), some will occur, some not.
    n_random = 80
    for _ in range(n_random):
        plen = rng.randint(1, 6)
        patterns.append(("random", bytes(rng.choice(b"ACGT") for _ in range(plen))))

    # 2) Random medium patterns (length 7..15)
    n_random = 60
    for _ in range(n_random):
        plen = rng.randint(7, 15)
        patterns.append(("random", bytes(rng.choice(b"ACGT") for _ in range(plen))))

    # 3) Random long patterns (length 16..40)
    n_random = 40
    for _ in range(n_random):
        plen = rng.randint(16, 40)
        patterns.append(("random", bytes(rng.choice(b"ACGT") for _ in range(plen))))

    # 4) Self-overlapping patterns: "A..A", "C..C" of various lengths
    for c in b"ACGT":
        for k in (2, 3, 5, 8, 12):
            patterns.append(("self_overlap_" + chr(c), bytes([c]) * k))

    # 5) Single-character: every base
    for c in b"ACGT":
        patterns.append(("single_char", bytes([c])))

    # 6) Patterns that touch the start of the text (boundary).
    for k in (1, 2, 4, 8):
        if k <= len(text):
            patterns.append(("prefix_boundary", text[:k]))
        if k <= len(text):
            patterns.append(("suffix_boundary", text[-k:]))

    # 7) Patterns that contain all 4 chars
    for _ in range(10):
        plen = rng.randint(4, 25)
        # force at least one of each A, C, G, T
        rest = [rng.choice(b"ACGT") for _ in range(plen - 4)]
        pat = bytes(list(b"ACGT") + rest)
        rng.shuffle(list(pat))
        patterns.append(("all_chars", bytes(pat)))

    # 8) Patterns with no occurrence.  Random 5-mers almost always occur in
    #    200 KB of random DNA, so we generate longer candidates and reject
    #    anything that actually appears.
    absent_added = 0
    target_absent = 30
    while absent_added < target_absent:
        plen = rng.randint(12, 60)
        cand = bytes(rng.choice(b"ACGT") for _ in range(plen))
        if text.find(cand) < 0:
            patterns.append(("absent", cand))
            absent_added += 1

    # 9) Empty pattern
    patterns.append(("empty", b""))

    return patterns


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------
def main() -> None:
    SEED = 1234
    TEXT_LEN = 200_000

    print("=" * 78)
    print("FM-index backward-search count -- correctness experiment")
    print("=" * 78)

    print(f"\n[1/4] Building text   (seed={SEED}, n={TEXT_LEN:,})")
    t0 = time.time()
    text = build_text(seed=SEED, n=TEXT_LEN)
    print(f"      text length       : {len(text):,} bytes")
    print(f"      alphabet          : {sorted(set(text))} -> {bytes(sorted(set(text)))!r}")
    print(f"      char distribution : {dict(Counter(text))}")
    print(f"      build time        : {time.time() - t0:.3f} s")

    print(f"\n[2/4] Building FM-index")
    t0 = time.time()
    fmi = FMIndex(text)
    t_build = time.time() - t0
    print(f"      |text+sentinel|   : {fmi.n:,}")
    print(f"      build time        : {t_build:.3f} s")
    print(f"      sentinel byte     : {fmi.text[0]}")
    print(f"      c_min             : {fmi.c_min}")
    print(f"      BWT first 20      : {fmi.bwt[:20].tolist()}")
    print(f"      SA  first 10      : {fmi.sa[:10].tolist()}")

    print(f"\n[3/4] Building pattern set   (seed={SEED})")
    patterns = build_patterns(seed=SEED, text=text)
    print(f"      total patterns    : {len(patterns)}")
    cat_counts = Counter(cat for cat, _ in patterns)
    for cat, n in sorted(cat_counts.items()):
        print(f"        {cat:20s} {n:4d}")

    print(f"\n[4/4] Comparing backward-search vs. brute-force  (overlapping)")
    matches = 0
    mismatches = 0
    rows: list[dict] = []
    for cat, pat in patterns:
        bf = brute_force_count_overlap(text, pat)
        bs = fmi.count(pat)
        ok = (bf == bs)
        if ok:
            matches += 1
        else:
            mismatches += 1
        rows.append({
            "category": cat,
            "pattern_hex": pat.hex(),
            "pattern_len": len(pat),
            "brute_force": bf,
            "backward_search": bs,
            "match": ok,
        })

    total = matches + mismatches
    print(f"\n      total queries       : {total}")
    print(f"      matches             : {matches}")
    print(f"      mismatches          : {mismatches}")
    print(f"      match rate          : {matches / total * 100:.4f}%")

    # show first 10 mismatches
    bad = [r for r in rows if not r["match"]]
    if bad:
        print(f"\n      First 10 mismatches:")
        for r in bad[:10]:
            print(f"        {r}")
    else:
        print(f"\n      (no mismatches)")

    # Quick timing comparison on a subset
    print(f"\n      Sample timing (per query, averaged over present random patterns)")
    t0 = time.time()
    for cat, pat in patterns[:200]:
        fmi.count(pat)
    t_bs = (time.time() - t0) / min(200, len(patterns))
    t0 = time.time()
    for cat, pat in patterns[:200]:
        brute_force_count_overlap(text, pat)
    t_bf = (time.time() - t0) / min(200, len(patterns))
    print(f"        backward search   : {t_bs * 1e6:9.2f} us")
    print(f"        brute force       : {t_bf * 1e6:9.2f} us")

    # Save results to JSON for the summary writer
    summary = {
        "seed": SEED,
        "text_length": TEXT_LEN,
        "alphabet": bytes(sorted(set(text))).decode(),
        "char_counts": dict(Counter(text)),
        "fmindex_build_time_s": t_build,
        "n_queries": total,
        "matches": matches,
        "mismatches": mismatches,
        "match_rate": matches / total,
        "per_category_match_rate": {
            cat: {
                "n": sum(1 for r in rows if r["category"] == cat),
                "matches": sum(1 for r in rows if r["category"] == cat and r["match"]),
                "mismatches": sum(1 for r in rows if r["category"] == cat and not r["match"]),
            }
            for cat in sorted(cat_counts.keys())
        },
        "first_mismatches": bad[:10],
    }
    with open("experiment_results.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n      results saved to experiment_results.json")


if __name__ == "__main__":
    main()
