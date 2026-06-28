import time, z3
from experiment import valid_magic_square  # reuse validator shape

def make_magic(n, target, timeout_ms=20000):
    """Build SAT and SMT encodings for an n x n magic square."""
    N = n*n
    VALUES = list(range(1, N+1))
    triples = []
    for r in range(n):
        triples.append([r*n+c for c in range(n)])
    for c in range(n):
        triples.append([r*n+c for r in range(n)])
    triples.append([i*n+i for i in range(n)])
    triples.append([i*n+(n-1-i) for i in range(n)])

    # ---- SAT ----
    def build_sat():
        s = z3.Solver(); s.set("timeout", timeout_ms)
        b = [[z3.Bool(f"b_{i}_{v}") for v in VALUES] for i in range(N)]
        ncv=0
        def add(cl):
            nonlocal ncv; s.add(cl); ncv+=1
        for i in range(N):
            add(z3.Or(b[i]))
            for p in range(len(VALUES)):
                for q in range(p+1,len(VALUES)):
                    add(z3.Or(z3.Not(b[i][p]),z3.Not(b[i][q])))
        for i in range(N):
            for j in range(i+1,N):
                for vi in range(len(VALUES)):
                    add(z3.Or(z3.Not(b[i][vi]),z3.Not(b[j][vi])))
        allowed=[t for t in __import__('itertools').product(VALUES,repeat=len(triples[0])) if sum(t)==target]
        naux=0
        for ti,tr in enumerate(triples):
            tvs=[]
            for tup in allowed:
                t=z3.Bool(f"t_{ti}_"+",".join(map(str,tup))); naux+=1; tvs.append(t)
                for k,idx in enumerate(tr):
                    add(z3.Or(z3.Not(t),b[idx][tup[k]-1]))
            add(z3.Or(tvs))
        def ext(m):
            out=[]
            for i in range(N):
                for vi in range(len(VALUES)):
                    if z3.is_true(m.eval(b[i][vi])): out.append(VALUES[vi]); break
            return out
        return s,ncv,N*len(VALUES)+naux,ext

    # ---- SMT ----
    def build_smt():
        s=z3.Solver(); s.set("timeout",timeout_ms)
        x=[z3.Int(f"x_{i}") for i in range(N)]; nc=0
        def add(c):
            nonlocal nc; s.add(c); nc+=1
        for i in range(N): add(z3.And(x[i]>=1,x[i]<=N))
        add(z3.Distinct(x))
        for tr in triples: add(sum(x[i] for i in tr)==target)
        def ext(m): return [m.eval(x[i]).as_long() for i in range(N)]
        return s,nc,N,ext

    return build_sat, build_smt, triples, target, N, VALUES

def trial(build, n=5):
    ts=[]; res=None; ext_solv=None
    for _ in range(n):
        s,nc,nv,ext=build()
        t0=time.perf_counter(); r=s.check(); t1=time.perf_counter()
        ts.append(t1-t0)
        if res is None: res=r; ext_solv=(ext,s)
    return str(r),ts,nc,nv,ext_solv

for n,target in [(3,15),(4,34)]:
    bsat,bsmt,triples,tgt,N,VALUES=make_magic(n,target)
    print(f"\n=== {n}x{n} magic square: {N} vars domain 1..{N}, {len(triples)} sum=={tgt} + alldiff ===")
    r,ts,nc,nv,es=trial(bsat)
    assign=es[0](es[1].model()) if r=="sat" else None
    print(f" SAT: {r} vars={nv} clauses={nc} times[min/med/max]={min(ts)*1000:.2f}/{sorted(ts)[len(ts)//2]*1000:.2f}/{max(ts)*1000:.2f} ms")
    if assign: print(f"      grid rows: {[assign[r*n:(r+1)*n] for r in range(n)]}")
    r,ts,nc,nv,es=trial(bsmt)
    assign=es[0](es[1].model()) if r=="sat" else None
    print(f" SMT: {r} intvars={nv} asserts={nc} times[min/med/max]={min(ts)*1000:.2f}/{sorted(ts)[len(ts)//2]*1000:.2f}/{max(ts)*1000:.2f} ms")
    if assign: print(f"      grid rows: {[assign[r*n:(r+1)*n] for r in range(n)]}")
