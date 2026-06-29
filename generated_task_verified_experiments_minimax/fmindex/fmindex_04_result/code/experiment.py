"""
FM-index "opportunistic / entropy-bounded" volume experiment.

We construct several equal-length texts whose empirical compressibility varies
(repetitive / periodic / skewed / random over small alphabet / natural English),
build the Burrows-Wheeler Transform for each, and measure how the *FM-index
size* (BWT run-length encoded body + small auxiliary summary) compares to the
*raw text size* (log2(|Sigma|) bits/symbol, the size of the uncompressed text).

The independent variable is the text's compressibility (0th-order empirical
entropy H_0(T) and gzip(T) size). All other settings are fixed:

    text length  N    = 2**20  bytes  (1 MiB)
    random seed       = 42
    auxiliary summary = C[0..sigma] cumulative-occurrence table
                        + Occ samples every sqrt(N) positions

The measurements are:
    * BWT run count r           (lower = more compressible; key FM-index param)
    * 0-th order empirical H_0  of T and of BWT(T)
    * gzip(T) and gzip(BWT)     bytes (a well-known compressibility proxy)
    * Theoretical FM-index bits = r * (log2(sigma) + log2(N/r))
                                   + (sigma+1) * log2(N)            (C table)
                                   + sigma * sqrt(N) * log2(N)       (Occ samples)
    * Index / text ratio        = |FM-index| bits / (N * log2|Sigma|) bits

The hypothesis is that the index/text ratio is close to 1 for incompressible
texts (random DNA) and drops toward 0 as the text becomes compressible, in
accordance with the theoretical O(H_k(T)) + o(1) bits/symbol bound of
Ferragina-Manzini (2000).
"""
from __future__ import annotations

import gzip
import json
import math
import os
import random
from collections import Counter
from typing import Iterable

import numpy as np
import PySAIS

# ---------------------------------------------------------------------------
# Fixed experiment settings
# ---------------------------------------------------------------------------
N = 1 << 20          # text length in bytes (1 MiB)
SEED = 42

DNA_ALPHABET = b"ACGT"
ENG_ALPHABET = (b"abcdefghijklmnopqrstuvwxyz ")


# ---------------------------------------------------------------------------
# Text generators (all length N, seed fixed)
# ---------------------------------------------------------------------------
def gen_random_dna(n: int, rng: random.Random) -> bytes:
    """Uniform i.i.d. over {A,C,G,T}. ~Incompressible on alphabet of size 4."""
    return bytes(rng.choices(DNA_ALPHABET, k=n))


def gen_periodic_dna(n: int) -> bytes:
    """Period-4 string ACGTACGT.... Highly compressible: r ~ sigma runs of BWT."""
    period = DNA_ALPHABET
    reps = n // len(period) + 1
    return (period * reps)[:n]


def gen_constant_dna(n: int) -> bytes:
    """A single repeated symbol. Maximally compressible: H_0 = 0."""
    return bytes([DNA_ALPHABET[0]]) * n


def gen_skewed_dna(n: int, rng: random.Random) -> bytes:
    """DNA with strong bias: 90% A, ~3.33% each of C, G, T."""
    probs = [0.90, 0.0333, 0.0333, 0.0334]
    return bytes(rng.choices(DNA_ALPHABET, weights=probs, k=n))


def gen_random_english(n: int, rng: random.Random) -> bytes:
    """Random over 27-letter alphabet with English-like distribution.
    Trained on the natural English sample to mirror its 0th-order profile,
    but with no higher-order structure (H_k = H_0 for all k)."""
    freqs = {
        ' ': 0.180,
        'e': 0.103, 't': 0.075, 'a': 0.064, 'o': 0.063, 'i': 0.057,
        'n': 0.057, 's': 0.052, 'h': 0.050, 'r': 0.045, 'd': 0.033,
        'l': 0.033, 'u': 0.023, 'c': 0.022, 'm': 0.020, 'w': 0.018,
        'f': 0.018, 'g': 0.016, 'y': 0.015, 'p': 0.014, 'b': 0.013,
        'v': 0.009, 'k': 0.007, 'j': 0.002, 'x': 0.002, 'q': 0.001,
        'z': 0.001,
    }
    letters = list(freqs.keys())
    weights = [freqs[c] for c in letters]
    return bytes(ord(c) for c in rng.choices(letters, weights=weights, k=n))


def gen_natural_english(n: int, corpus_path: str) -> bytes:
    """n bytes of real natural English text, taken cyclically from a corpus."""
    with open(corpus_path, "rb") as f:
        corpus = f.read()
    if len(corpus) < n:
        reps = (n // len(corpus)) + 1
        corpus = (corpus * reps)[: n + len(corpus)]
    return corpus[:n]


# ---------------------------------------------------------------------------
# Compressibility / entropy / index-size measurements
# ---------------------------------------------------------------------------
def shannon_h0(data) -> float:
    """0-th order empirical entropy in bits/symbol."""
    if isinstance(data, (bytes, bytearray)):
        counts = Counter(data)
    else:
        arr = np.asarray(data)
        counts = Counter(arr.tolist())
    n = sum(counts.values())
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * math.log2(p)
    return h


def count_runs(data) -> int:
    """Number of maximal runs of equal symbols (used as proxy for BWT runs)."""
    if isinstance(data, (bytes, bytearray)):
        it = iter(data)
    else:
        it = iter(np.asarray(data).tolist())
    try:
        prev = next(it)
    except StopIteration:
        return 0
    runs = 1
    for b in it:
        if b != prev:
            runs += 1
            prev = b
    return runs


def gzip_bits(data: bytes) -> int:
    return len(gzip.compress(data, compresslevel=9)) * 8


def bwt(data: bytes) -> np.ndarray:
    """BWT via SA-IS. Returns a uint8 array of length |T|.
    Sentinel 0x00 is appended internally (it sorts before every other byte
    used in our texts) and the sentinel row is dropped from the output."""
    augmented = data + b"\x00"
    sa = PySAIS.sais(augmented)
    n = len(augmented)
    out = np.empty(n, dtype=np.uint8)
    for i in range(n):
        sa_i = int(sa[i])
        out[i] = augmented[sa_i - 1] if sa_i > 0 else augmented[n - 1]
    return out[:-1]


def mtf_transform(bwt_arr: np.ndarray, sigma: int) -> np.ndarray:
    """Move-to-front: replace each byte by its rank in the current MTF list."""
    mtf = np.arange(sigma, dtype=np.int64)
    out = np.empty(len(bwt_arr), dtype=np.int64)
    for i, c in enumerate(bwt_arr):
        r = int(np.where(mtf == c)[0][0])
        out[i] = r
        if r > 0:
            mtf[1:r + 1] = mtf[0:r]
            mtf[0] = c
    return out


def run_lengths(bwt_arr: np.ndarray) -> np.ndarray:
    """Return the lengths of consecutive-equal runs in bwt_arr."""
    if len(bwt_arr) == 0:
        return np.zeros(0, dtype=np.int64)
    changes = np.where(np.diff(bwt_arr) != 0)[0] + 1
    boundaries = np.concatenate(([0], changes, [len(bwt_arr)]))
    return np.diff(boundaries)


def fm_index_bits(text_bytes: bytes, sigma_for_text: int) -> dict:
    """Compute BWT, derive compressibility proxies, and estimate FM-index size
    in bits using the standard run-based decomposition."""
    bwt_arr = bwt(text_bytes)
    sigma_bwt = int(bwt_arr.max()) + 1
    sigma_bwt = max(sigma_bwt, 2)
    r = count_runs(bwt_arr)
    h0_bwt = shannon_h0(bwt_arr)
    rlens = run_lengths(bwt_arr)
    avg_rlen = float(rlens.mean())
    max_rlen = int(rlens.max())

    # 1) gzip(BWT) — practical upper bound on what BW_RLX can deliver.
    gz_bwt_bits = gzip_bits(bytes(bwt_arr))

    # 2) gzip(MTF(BWT)) — what BW_RLX-style coding can typically achieve.
    mtf_arr = mtf_transform(bwt_arr, sigma_bwt)
    gz_mtf_bits = gzip_bits(mtf_arr.astype(np.uint8).tobytes())

    # 3) Honest run-length-encoded body bits:
    #    Each BWT run encodes (character, run-length). The character costs
    #    ceil(log2 sigma) bits; the run-length costs ceil(log2 (rlen+1)) bits.
    char_bits_per_run = math.ceil(math.log2(sigma_bwt))
    body_rle_bits = int(
        r * char_bits_per_run + sum(int(math.ceil(math.log2(rl + 1)))
                                    for rl in rlens)
    )

    # 4) Information-theoretic lower bound on body size (unreachable in
    #    practice but the true entropy floor):
    body_entropy_floor_bits = int(math.ceil(N * h0_bwt))

    # 5) Auxiliary: C table + Occ samples.
    log_n = N.bit_length()
    aux_c = (sigma_bwt + 1) * log_n
    sample_step = max(1, int(math.isqrt(N)))
    n_samples = N // sample_step + 1
    aux_occ = sigma_bwt * n_samples * log_n
    aux_total = aux_c + aux_occ

    # The "FM-index size" reported is the run-length-encoded body + auxiliary,
    # which is the standard "FM-index volume" decomposition from
    # Ferragina-Manzini (2000). We also report the entropy floor and gzip
    # numbers for context.
    fm_index_bits_value = body_rle_bits + aux_total
    fm_index_bits_lowerbound = body_entropy_floor_bits + aux_total

    text_bits_uncoded = N * math.ceil(math.log2(sigma_for_text))
    text_bits_raw = 8 * N
    text_bits_entropy_floor = int(math.ceil(N * shannon_h0(text_bytes)))

    return {
        "text_bytes": N,
        "text_sigma": sigma_for_text,
        "text_bits_uncoded": text_bits_uncoded,
        "text_bits_raw": text_bits_raw,
        "text_bits_entropy_floor": text_bits_entropy_floor,
        "text_h0": shannon_h0(text_bytes),
        "text_gzip_bits": gzip_bits(text_bytes),
        "bwt_h0": h0_bwt,
        "bwt_runs": r,
        "bwt_avg_run_len": avg_rlen,
        "bwt_max_run_len": max_rlen,
        "bwt_gzip_bits": gz_bwt_bits,
        "mtf_gzip_bits": gz_mtf_bits,
        "body_rle_bits": body_rle_bits,
        "body_entropy_floor_bits": body_entropy_floor_bits,
        "aux_c_bits": aux_c,
        "aux_occ_bits": aux_occ,
        "aux_total_bits": aux_total,
        "fm_index_bits": fm_index_bits_value,
        "fm_index_bits_lowerbound": fm_index_bits_lowerbound,
        "ratio_to_uncoded": fm_index_bits_value / text_bits_uncoded,
        "ratio_to_raw": fm_index_bits_value / text_bits_raw,
        # Information-rate proxies (bits per input symbol):
        "bps_body_rle": body_rle_bits / N,
        "bps_body_gzip_bwt": gz_bwt_bits / N,
        "bps_body_gzip_mtf": gz_mtf_bits / N,
        "bps_text_h0": shannon_h0(text_bytes),
        "bps_bwt_h0": h0_bwt,
        "bps_text_gzip": gzip_bits(text_bytes) / N,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    rng = random.Random(SEED)
    np.random.seed(SEED)

    eng_corpus = "/tmp/english.txt"

    samples = []
    print(f"# Generating {N} bytes per text type (seed={SEED})")

    t = gen_random_dna(N, rng)
    samples.append(("random_dna", t, 4))
    del t

    t = gen_periodic_dna(N)
    samples.append(("periodic_dna_acgt", t, 4))
    del t

    t = gen_constant_dna(N)
    samples.append(("constant_a", t, 4))
    del t

    t = gen_skewed_dna(N, rng)
    samples.append(("skewed_dna", t, 4))
    del t

    t = gen_random_english(N, rng)
    samples.append(("random_english_1gram", t, 27))
    del t

    t = gen_natural_english(N, eng_corpus)
    samples.append(("natural_english", t, 27))
    del t

    results = []
    for name, text, sigma in samples:
        print(f"# Computing BWT + FM-index for: {name}")
        info = fm_index_bits(text, sigma)
        info["name"] = name
        results.append(info)
        del text

    with open("results.json", "w") as f:
        json.dump(results, f, indent=2, default=float)

    # Pretty summary
    print("\n=== SUMMARY (N = %d = %.1f MB) ===" % (N, N / 1024 / 1024))
    header = (f"{'name':<24} {'H0(T)':>6} {'gzip(T)':>9} "
              f"{'r':>8} {'H0(BWT)':>8} {'avg_run':>8} "
              f"{'gzipBWT':>9} {'gzipMTF':>9} "
              f"{'RLE b/s':>8} {'gz b/s':>8} "
              f"{'body MB':>8} {'aux MB':>8} {'FM MB':>8} "
              f"{'r_ucd':>7} {'r_raw':>7}")
    print(header)
    for r in results:
        print(f"{r['name']:<24} "
              f"{r['text_h0']:>6.2f} "
              f"{r['text_gzip_bits']/8/1024:>8.1f}K "
              f"{r['bwt_runs']:>8d} {r['bwt_h0']:>8.2f} "
              f"{r['bwt_avg_run_len']:>8.2f} "
              f"{r['bwt_gzip_bits']/8/1024:>8.1f}K "
              f"{r['mtf_gzip_bits']/8/1024:>8.1f}K "
              f"{r['bps_body_rle']:>8.3f} "
              f"{r['bps_body_gzip_mtf']:>8.3f} "
              f"{r['body_rle_bits']/8/1024/1024:>7.3f}M "
              f"{r['aux_total_bits']/8/1024/1024:>7.3f}M "
              f"{r['fm_index_bits']/8/1024/1024:>7.3f}M "
              f"{r['ratio_to_uncoded']:>7.3f} "
              f"{r['ratio_to_raw']:>7.3f}")


if __name__ == "__main__":
    main()