import heapq, numpy as np
from collections import Counter

N=1_000_000; SEED=42
def ss(stream,k):
    count={}; heap=[]
    for e in stream:
        c=count.get(e)
        if c is not None:
            c+=1; count[e]=c; heapq.heappush(heap,(c,e))
        elif len(count)<k:
            count[e]=1; heapq.heappush(heap,(1,e))
        else:
            while heap:
                minv,me=heapq.heappop(heap)
                if count.get(me)==minv: break
            del count[me]; count[e]=minv+1
            heapq.heappush(heap,(minv+1,e))
    # min
    mn=min(count.values())
    return count,mn

for alpha in [1.1,1.3,1.5,1.8,2.0]:
    rng=np.random.default_rng(SEED)
    stream=rng.zipf(alpha,size=N).astype(np.int64).tolist()
    exact=Counter(stream)
    items=sorted(exact.items(),key=lambda kv:(-kv[1],kv[0]))
    for k in [50,100,200,500]:
        est,mn=ss(stream,k)
        rep=sorted(est.items(),key=lambda kv:(-kv[1],kv[0]))
        rep_set=set(it for it,_ in rep[:k])
        true_set=set(it for it,_ in items[:k])
        ov=len(rep_set&true_set)
        # tie-aware: f*_k
        fk=items[k-1][1]
        true_ge=set(it for it,c in items if c>fk)   # strictly above boundary
        n_tied=sum(1 for it,c in items if c==fk)
        true_geq=true_ge | set(it for it,c in items if c==fk)  # all tied-or-above
        rep_correct_tie=sum(1 for it in rep_set if exact.get(it,0)>=fk)
        prec_tie=rep_correct_tie/len(rep_set)
        rec_tie=rep_correct_tie/len(true_geq)
        maxover=max(cnt-exact.get(e,0) for e,cnt in est.items())
        print(f"a={alpha} k={k:3d} strict P=R={ov/k:.3f} | tie P={prec_tie:.3f} R={rec_tie:.3f} (n_geq={len(true_geq)},tied={n_tied}) | maxover={maxover} N/k={N/k:.0f} f*_k={fk}")
    print()
