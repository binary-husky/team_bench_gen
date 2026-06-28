#!/usr/bin/env python3
"""
FM-index opportunistic / entropy-bounded size experiment.

Goal (from task.md): construct several equal-length texts of differing
compressibility, build the BWT of each, and measure "index volume vs text
volume" as a function of compressibility. We measure:
  - 0-th / k-th order empirical entropy of the text  (compressibility proxy)
  - number of runs of the BWT  r
  - 0-th order empirical entropy of the BWT
  - bit size of the BW_RLX pipeline (bwt + mtf + rle-of-zero-runs + PC),
    which is the FM-index core whose size the paper bounds by
        |BW_RLX(T)| <= 5 |T| H_k(T) + g_k log |T|     (Ferragina-Manzini Eq.1)
Index/text ratios are reported against both the native alphabet rate
(n * log2(sigma) bits) and the raw byte rate (n * 8 bits).
"""
import numpy as np
import math, json, os

SEED = 12345
rng = np.random.default_rng(SEED)

# ----------------------------------------------------------------------------
# Suffix array (prefix doubling, O(n log n) with numpy radix/lexsort) + BWT
# ----------------------------------------------------------------------------
def suffix_array(s):
    """s: numpy array of small ints (0..sigma-1). Returns SA of s (no sentinel)."""
    n = s.shape[0]
    sa = np.arange(n, dtype=np.int64)
    rank = s.astype(np.int64).copy()
    tmp = np.empty(n, dtype=np.int64)
    k = 1
    # initial sort by first char
    sa = np.lexsort((np.zeros(n,dtype=np.int64), rank)) if False else np.argsort(rank, kind='stable')
    rank = rank[sa]
    # build rank array indexed by original position
    rpos = np.empty(n, dtype=np.int64)
    cur = 0
    rpos[sa[0]] = 0
    for i in range(1, n):
        if rank[i] != rank[i-1]:
            cur += 1
        rpos[sa[i]] = cur
    rank = rpos
    while k < n:
        # sort by (rank[i], rank2[i]) where rank2[i] = rank[i+k] or -1 if out
        rank2 = np.full(n, -1, dtype=np.int64)
        mask = (np.arange(n) + k) < n
        rank2[mask] = rank[np.arange(n)[mask] + k]
        # numpy lexsort: last key is primary -> put rank primary last
        sa = np.lexsort((rank2, rank))
        # recompute ranks
        new_rank = np.empty(n, dtype=np.int64)
        new_rank[sa[0]] = 0
        prev_r = rank[sa[0]]; prev_r2 = rank2[sa[0]]
        cur = 0
        rr = rank[sa]; rr2 = rank2[sa]
        diff = (rr[1:] != rr[:-1]) | (rr2[1:] != rr2[:-1])
        # cumulative
        new_rank[sa[1:]] = np.cumsum(diff)
        rank = new_rank
        if rank[sa[-1]] == n - 1:
            break
        k *= 2
    return sa

def bwt(s):
    """BWT of byte/int array s. Append unique sentinel 0 (lex smallest), use BWT of s+'#'.
    We use a larger-than-alphabet sentinel so all original symbols > sentinel.
    Returns (L_without_sentinel_runs_info, L array of length n with sentinel handling).
    Standard: SA of T = s + [sentinel]; L[i] = T[SA[i]-1] (with T[-1]=sentinel).
    """
    sigma = int(s.max())+1
    sentinel = sigma  # unique, lex-smallest among used
    T = np.empty(s.shape[0]+1, dtype=np.int64)
    T[:s.shape[0]] = s
    T[-1] = sentinel
    sa = suffix_array(T)
    # L[i] = T[sa[i]-1] ; for sa[i]==0 -> sentinel
    prev = (sa - 1) % T.shape[0]
    L = T[prev]
    # drop the sentinel column position for run counting: keep full L (incl sentinel)
    return L, sa, sigma+1  # alphabet incl sentinel

# ----------------------------------------------------------------------------
# Entropy
# ----------------------------------------------------------------------------
def H0(arr):
    n = arr.shape[0]
    vals, counts = np.unique(arr, return_counts=True)
    p = counts / n
    p = p[p>0]
    return float(-(p*np.log2(p)).sum())

def Hk(arr, k):
    """k-th order empirical entropy (k>=0). H0 special-cased."""
    n = arr.shape[0]
    if k == 0:
        return H0(arr)
    # build context of length k (preceding k chars); for the first k chars context is shorter -> use
    # standard definition: sum over all contexts c of (|c|/n) * H0(string following c)
    # We use a sliding context of exactly k preceding symbols; positions with <k preceding are treated
    # with their available shorter context (pad). To keep it simple & standard we use contexts of length
    # up to k via tuple of the k preceding symbols (None padded). Each distinct prefix-context handled.
    from collections import defaultdict
    ctx = defaultdict(list)
    for i in range(n):
        # context = preceding k symbols (None if out of range)
        c = tuple(int(arr[j]) for j in range(max(0,i-k), i))
        ctx[c].append(int(arr[i]))
    H = 0.0
    for c, syms in ctx.items():
        m = len(syms)
        if m == 0: continue
        a = np.array(syms)
        vals, cnts = np.unique(a, return_counts=True)
        p = cnts / m
        h = -(p*np.log2(p)).sum()
        H += (m/n)*h
    return float(H)

# ----------------------------------------------------------------------------
# BW_RLX pipeline: bwt -> mtf -> rle(zero runs) -> PC code. Returns bit length.
# ----------------------------------------------------------------------------
def mtf_encode(s):
    """Move-to-front over alphabet 0..sigma-1 (int list). Returns list of mtf codes."""
    alpha = list(range(int(max(s))+1))
    out = []
    for c in s:
        idx = alpha.index(c)
        out.append(idx)
        if idx:
            del alpha[idx]; alpha.insert(0, c)
    return out

def rle_zero_runs(mtf):
    """Replace run 0^m (m>=1) with binary rep of (m+1) LSB-first discarding MSB.
    Emit bit-symbols: '0' or '1'. Non-zero mtf symbols kept as themselves (>=1).
    Returns list over alphabet {0b,1b, 1,2,...,sigma-1}."""
    out = []
    i = 0
    n = len(mtf)
    while i < n:
        if mtf[i] == 0:
            j = i
            while j < n and mtf[j] == 0:
                j += 1
            m = j - i
            # binary of (m+1), LSB first, drop MSB
            v = m + 1
            bits = []
            x = v
            while x > 0:
                bits.append(x & 1)
                x >>= 1
            bits = bits[:-1]  # drop MSB
            out.extend(bits)
            i = j
        else:
            out.append(mtf[i])
            i += 1
    return out

def pc_bits(sym):
    """PC code length. bit-symbols 0/1 -> 2 bits; mtf symbol i>=1 -> 1+2*floor(log2(i+1)) bits."""
    if sym == 0 or sym == 1:
        # ambiguous: we tagged bit-symbols separately. We'll pass a tag.
        return 2
    return 1 + 2*int(math.floor(math.log2(sym+1)))

def bw_rlx_bits(L, sigma):
    """Full BW_RLX bit length for BWT L (int array incl sentinel)."""
    mtf = mtf_encode(L.tolist())
    rl = rle_zero_runs(mtf)
    # distinguish bit-symbols from mtf symbols: rle emits 0/1 ints that MEAN bits,
    # and mtf symbols >=1. But mtf symbol could be 1 too! Ambiguity is resolved in the
    # paper by using distinct alphabet for bit-symbols. We track types explicitly.
    total = 0
    for s in rl:
        if isinstance(s, tuple):  # bit symbol
            total += 2
        else:  # mtf symbol >=1
            total += 1 + 2*int(math.floor(math.log2(s+1)))
    return total

# Re-emit rle with tagged bit symbols
def rle_zero_runs_tagged(mtf):
    out = []
    i = 0; n = len(mtf)
    while i < n:
        if mtf[i] == 0:
            j = i
            while j < n and mtf[j] == 0:
                j += 1
            m = j - i
            v = m + 1
            bits = []
            x = v
            while x > 0:
                bits.append(x & 1); x >>= 1
            bits = bits[:-1]
            out.extend(('BIT', b) for b in bits)
            i = j
        else:
            out.append(('MTF', mtf[i]))
            i += 1
    return out

def bw_rlx_bits_v2(L):
    mtf = mtf_encode(L.tolist())
    rl = rle_zero_runs_tagged(mtf)
    total = 0
    for tag, v in rl:
        if tag == 'BIT':
            total += 2
        else:
            total += 1 + 2*int(math.floor(math.log2(v+1)))
    return total

def run_count(L):
    a = np.asarray(L)
    return int((a[1:] != a[:-1]).sum()) + 1

# ----------------------------------------------------------------------------
# Text generators (all length N)
# ----------------------------------------------------------------------------
DNA = np.array(list("ACGT"))

def gen_random_dna(n):
    idx = rng.integers(0,4,size=n)
    return DNA[idx]

def gen_repetitive_dna(n, motif_len=32, n_motifs=1):
    # 1 motif repeated -> maximally compressible
    motifs = [DNA[rng.integers(0,4,size=motif_len)] for _ in range(n_motifs)]
    out = []
    while len(out) < n:
        m = motifs[rng.integers(0, n_motifs)]
        out.append(m)
    arr = np.concatenate(out)[:n]
    return arr

def gen_semirep_dna(n, motif_len=8, n_motifs=16):
    # several motifs -> moderately compressible
    motifs = [DNA[rng.integers(0,4,size=motif_len)] for _ in range(n_motifs)]
    out = []
    while len(out) < n:
        m = motifs[rng.integers(0, n_motifs)]
        out.append(m)
    arr = np.concatenate(out)[:n]
    return arr

def gen_english(n):
    txt = open('alice_clean.txt','r',encoding='utf-8').read()
    # take first n chars
    s = txt[:n]
    # encode as bytes (ascii printable 32..126) -> alphabet of ~95 symbols
    b = s.encode('ascii','ignore')
    return np.array(list(b), dtype=np.int64)

def text_to_int_array(s_bytes_or_str, mapping=None):
    pass

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def measure(name, arr):
    n = arr.shape[0]
    # map to 0..sigma-1 contiguous
    vals = np.unique(arr)
    remap = {v:i for i,v in enumerate(vals)}
    arr = np.array([remap[v] for v in arr], dtype=np.int64)
    sigma = len(vals)
    H0t = H0(arr)
    H2t = Hk(arr, 2)
    H3t = Hk(arr, 3)
    # BWT
    L, sa, sigma_with_sentinel = bwt(arr)
    r = run_count(L)
    H0L = H0(L)
    rlx_bits = bw_rlx_bits_v2(L)
    native_text_bits = n * math.log2(sigma) if sigma>1 else n  # fixed-length optimal encoding
    byte_text_bits = n * 8
    res = dict(
        name=name, n=int(n), sigma=int(sigma),
        H0_text=H0t, H2_text=H2t, H3_text=H3t,
        bwt_runs=int(r), H0_bwt=H0L,
        bw_rlx_bits=int(rlx_bits),
        native_text_bits=float(native_text_bits),
        byte_text_bits=float(byte_text_bits),
        ratio_rlx_vs_native = rlx_bits/native_text_bits,
        ratio_rlx_vs_byte = rlx_bits/byte_text_bits,
        rlx_bits_per_symbol = rlx_bits/n,
        runs_per_symbol = r/n,
    )
    return res

def main():
    N = 65536
    texts = [
        ("random DNA (incompressible)", gen_random_dna(N)),
        ("semi-repetitive DNA (16 motifs)", gen_semirep_dna(N, motif_len=8, n_motifs=16)),
        ("repetitive DNA (1 motif)", gen_repetitive_dna(N, motif_len=32, n_motifs=1)),
        ("English text (Alice)", gen_english(N)),
    ]
    results = []
    for name, arr in texts:
        print(f"measuring {name} (n={arr.shape[0]})...")
        res = measure(name, arr)
        results.append(res)
    # sort by H0_text ascending (most compressible first) for the table
    results_sorted = sorted(results, key=lambda r: r['H0_text'])
    print("\n=== RESULTS ===")
    for r in results_sorted:
        print(json.dumps(r, indent=0))
    with open('results.json','w') as f:
        json.dump(results_sorted, f, indent=2)
    # also a readable table
    cols = ['name','n','sigma','H0_text','H2_text','H3_text','bwt_runs','runs_per_symbol','H0_bwt','bw_rlx_bits','ratio_rlx_vs_native','ratio_rlx_vs_byte','rlx_bits_per_symbol']
    with open('results_table.txt','w') as f:
        f.write('\t'.join(cols)+'\n')
        for r in results_sorted:
            f.write('\t'.join(f"{r[c]:.4g}" if isinstance(r[c],float) else str(r[c]) for c in cols)+'\n')
    print("\nWrote results.json and results_table.txt")

if __name__ == '__main__':
    main()
