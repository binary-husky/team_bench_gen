import mmh3, random, array, sys, time

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
        return v if v != 0 else 1

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
        # try i1
        s, e = self._slots(i1)
        for j in range(s, e):
            if table[j] == 0:
                table[j] = fp
                return True
        # try i2
        s, e = self._slots(i2)
        for j in range(s, e):
            if table[j] == 0:
                table[j] = fp
                return True
        # kick
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
        occ = sum(1 for x in self.table if x != 0)
        return occ / len(self.table)


def run(M, b, f, seed, N):
    cf = CuckooFilter(M, b, f, seed)
    keys = [str(i).encode() for i in range(N)]
    fails = 0
    for k in keys:
        if not cf.insert(k):
            fails += 1
    # FPR: query non-members N..2N-1
    fp_count = 0
    for i in range(N, 2 * N):
        if cf.contains(str(i).encode()):
            fp_count += 1
    return cf.load(), fails, fp_count / N, cf.kicks


if __name__ == '__main__':
    M = 1 << 16
    b = 4
    N = 200000
    for f in [4]:
        for seed in range(3):
            t0 = time.time()
            load, fails, fpr, kicks = run(M, b, f, seed, N)
            print(f"f={f} seed={seed} M={M} load={load:.4f} fails={fails} FPR={fpr:.6f} kicks={kicks} t={time.time()-t0:.1f}s")
