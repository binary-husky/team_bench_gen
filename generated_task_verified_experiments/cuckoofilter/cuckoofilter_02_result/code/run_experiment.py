import mmh3, random, array, time, statistics, json

class CuckooFilter:
    __slots__ = ('M','b','f','maskM','maskf','table','rng','sA','sB','sC','kicks')
    def __init__(self, M, b, f, seed):
        assert M & (M-1) == 0, "M must be power of 2"
        self.M = M; self.b = b; self.f = f
        self.maskM = M - 1
        self.maskf = (1 << f) - 1
        self.table = array.array('H', [0]) * (M * b)
        self.rng = random.Random(seed * 2654435761 + 12345)
        self.sA = (seed * 7 + 1) & 0x7fffffff
        self.sB = (seed * 13 + 5) & 0x7fffffff
        self.sC = (seed * 31 + 9) & 0x7fffffff
        self.kicks = 0

    def _i1(self, key):
        return mmh3.hash128(key, self.sA, signed=False) & self.maskM

    def _fp(self, key):
        v = mmh3.hash128(key, self.sB, signed=False) & self.maskf
        return v if v != 0 else 1  # nonzero: 0 means empty slot

    def _hfp(self, fp):
        return mmh3.hash128(fp.to_bytes(8, 'little'), self.sC, signed=False) & self.maskM

    def _slots(self, i):
        b = self.b
        base = i * b
        return base, base + b

    def insert(self, key):
        b = self.b
        table = self.table
        i1 = self._i1(key)
        fp = self._fp(key)
        i2 = i1 ^ self._hfp(fp)
        s, e = self._slots(i1)
        for j in range(s, e):
            if table[j] == 0:
                table[j] = fp
                return True
        s, e = self._slots(i2)
        for j in range(s, e):
            if table[j] == 0:
                table[j] = fp
                return True
        MAXK = 500
        rng = self.rng
        i = i1 if rng.random() < 0.5 else i2
        for _ in range(MAXK):
            s, e = self._slots(i)
            j = rng.randrange(s, e)
            fp, table[j] = table[j], fp
            self.kicks += 1
            i = i ^ self._hfp(fp)
            s, e = self._slots(i)
            for k in range(s, e):
                if table[k] == 0:
                    table[k] = fp
                    return True
        return False

    def contains(self, key):
        b = self.b
        table = self.table
        i1 = self._i1(key)
        fp = self._fp(key)
        i2 = i1 ^ self._hfp(fp)
        s, e = self._slots(i1)
        for j in range(s, e):
            if table[j] == fp:
                return True
        s, e = self._slots(i2)
        for j in range(s, e):
            if table[j] == fp:
                return True
        return False

    def load(self):
        occ = 0
        for x in self.table:
            if x != 0:
                occ += 1
        return occ / len(self.table)


def run(M, b, f, seed, N):
    cf = CuckooFilter(M, b, f, seed)
    fails = 0
    for i in range(N):
        if not cf.insert(str(i).encode()):
            fails += 1
    fp_count = 0
    for i in range(N, 2 * N):
        if cf.contains(str(i).encode()):
            fp_count += 1
    return {
        'load': cf.load(),
        'fails': fails,
        'fpr': fp_count / N,
        'kicks': cf.kicks,
    }


if __name__ == '__main__':
    M = 1 << 16          # 65536 buckets, power of two (clean XOR indexing)
    b = 4
    N = 200000
    SEEDS = list(range(10))
    F_LIST = [4, 8, 12, 16]

    results = {}
    for f in F_LIST:
        runs = []
        for seed in SEEDS:
            t0 = time.time()
            r = run(M, b, f, seed, N)
            r['seed'] = seed
            r['t'] = time.time() - t0
            runs.append(r)
        results[f] = runs
        fprs = [x['fpr'] for x in runs]
        loads = [x['load'] for x in runs]
        print(f"f={f:2d}  load={statistics.mean(loads):.4f} (±{statistics.pstdev(loads):.5f})  "
              f"FPR={statistics.mean(fprs):.6f} (±{statistics.pstdev(fprs):.6f})  "
              f"maxfails={max(x['fails'] for x in runs)}  t={statistics.mean(x['t'] for x in runs):.2f}s")

    json.dump({'M': M, 'b': b, 'N': N, 'seeds': SEEDS, 'results': results},
              open('results.json', 'w'), indent=2)
    print("wrote results.json")
