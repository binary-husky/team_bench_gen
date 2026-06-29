"""Quick ablation: confirm that cuckoo-filter false-negatives come from
fingerprint collisions, by re-running the experiment with several f values
and the same N, b, m, seed."""
import json
from experiment import CuckooFilter, make_keys, N, B, MAX_KICKS, HALF, SEED
import random

results = []
for F_BITS in (8, 10, 12, 14, 16):
    m = 32_768  # power of 2, so XOR alt-index round-trips
    cf = CuckooFilter(m, b=B, f=F_BITS, max_kicks=MAX_KICKS)
    keys = make_keys(N, SEED)
    insert_failures = 0
    for k in keys:
        if not cf.insert(k):
            insert_failures += 1
    rng = random.Random(SEED)
    shuffled = list(keys)
    rng.shuffle(shuffled)
    retained, deleted = shuffled[:HALF], shuffled[HALF:]
    for k in deleted:
        cf.delete(k)
    fn_rate = (HALF - sum(1 for k in retained if cf.lookup(k))) / HALF
    fpr_rate = sum(1 for k in make_keys(N, SEED + 1) if cf.lookup(k)) / N
    results.append(dict(f=F_BITS, m=m, b=B, N=N,
                        insert_failures=insert_failures,
                        false_negative_rate=fn_rate,
                        fpr_fresh=fpr_rate,
                        n_unique_fps=2 ** F_BITS,
                        avg_collisions_per_fp=N / (2 ** F_BITS)))
    print(f"f={F_BITS:2d}  |FPs|={2**F_BITS:5d}  avg_col/fp={N/(2**F_BITS):7.2f}  "
          f"ins_fail={insert_failures}  FNR={fn_rate:.4f}  FPR={fpr_rate:.4f}")

with open("sweep_f.json", "w") as f:
    json.dump(results, f, indent=2)
