"""Additional sanity checks for LF-mapping reversibility.

Confirms the result is not just lucky on one (text, seed) pair, by also
reconstructing across the four corners of the requested size window
(100 KiB and 500 KiB) and on a short stress text that mixes all byte
values.
"""
import os
import random
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lf_mapping_experiment import (
    bwt, build_C_and_rank, reconstruct, ALPHABET, SEED,
)


def run_case(name, text, sigma=255):
    t0 = time.perf_counter()
    L = bwt(text, sentinel=0)
    t_bwt = time.perf_counter() - t0
    t0 = time.perf_counter()
    C, rank = build_C_and_rank(L, sigma)
    t_aux = time.perf_counter() - t0
    t0 = time.perf_counter()
    rec = reconstruct(L, C, rank)
    t_recon = time.perf_counter() - t0

    n = len(text)
    first_mismatch = -1
    for i in range(n):
        if rec[i] != text[i]:
            first_mismatch = i
            break
    equal = (first_mismatch == -1)
    print(f"{name:24s} len={n:7d}  equal={equal}  "
          f"first_mismatch={first_mismatch}  "
          f"bwt={t_bwt*1000:7.1f}ms  aux={t_aux*1000:6.2f}ms  "
          f"recon={t_recon*1000:6.2f}ms")
    return equal


def main():
    rng = random.Random(SEED)
    results = []
    # lower / middle / upper edge of the 100KB-500KB window.
    results.append(run_case(
        "100KB random",
        bytes(rng.choice(ALPHABET) for _ in range(100 * 1024)),
    ))
    results.append(run_case(
        "200KB random (main)",
        bytes(rng.choice(ALPHABET) for _ in range(200 * 1024)),
    ))
    results.append(run_case(
        "500KB random",
        bytes(rng.choice(ALPHABET) for _ in range(500 * 1024)),
    ))
    # full-byte alphabet stress: every byte value appears, sentinel (0) excluded.
    stress = bytes((i % 255) + 1 for i in range(150 * 1024))
    results.append(run_case("150KB all-bytes", stress))

    # tiny regression check
    results.append(run_case("text='hello'", b"hello"))

    print("ALL OK" if all(results) else "FAILURES PRESENT")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
