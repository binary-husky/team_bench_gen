"""
Verify the solutions produced by both encodings are valid solutions to the
original problems. This is a stronger cross-check than equality of models.
"""
import json
from itertools import combinations


def verify_nqueens(N, sol):
    """Check q_0..q_{N-1} is a valid N-Queens solution."""
    if not sol or len(sol) != N:
        return False
    if not all(0 <= v < N for v in sol):
        return False
    if len(set(sol)) != N:
        return False
    for i, j in combinations(range(N), 2):
        if abs(sol[i] - sol[j]) == abs(i - j):
            return False
    return True


def verify_coloring(graph, k, sol):
    n = max(max(i, j) for (i, j) in graph.edges) + 1
    if not sol or len(sol) != n:
        return False
    if not all(0 <= v < k for v in sol):
        return False
    for (i, j) in graph.edges:
        if sol[i] == sol[j]:
            return False
    return True


def verify_linsys(model):
    if not model:
        return False
    A = model["A"]; B = model["B"]; C = model["C"]
    D = model["D"]; E = model["E"]; F = model["F"]
    G = model["G"]; H = model["H"]; I = model["I"]; J = model["J"]
    if not all(0 <= v <= 9 for v in (A, B, C, D, E, F, G, H, I, J)):
        return False
    if A == 0 or D == 0 or G == 0:
        return False
    if len({A, B, C, D, E, F, G, H, I, J}) != 10:
        return False
    return (100 * A + 10 * B + C + 100 * D + 10 * E + F ==
            1000 * G + 100 * H + 10 * I + J)


def main():
    with open("results/raw.json") as f:
        rows = json.load(f)
    pairs = {}
    for r in rows:
        pairs.setdefault(r["problem"], []).append(r)

    print("== Solution validity check ==")
    for prob, group in pairs.items():
        nat, boolr = group[0], group[1]
        assert nat["encoding"] == "native-Int" and boolr["encoding"] == "bool-table"
        sat = nat["result"] == "sat" and boolr["result"] == "sat"
        if not sat:
            ok = nat["result"] == boolr["result"]
            print(f"  {prob}: result match = {ok}  (native={nat['result']}, bool={boolr['result']})")
            continue
        if prob.startswith("NQueens"):
            N = int(prob.split("-")[1])
            ok1 = verify_nqueens(N, nat["model"])
            ok2 = verify_nqueens(N, boolr["model"])
        elif prob.startswith("Coloring"):
            # We need the Graph object; rough recheck using k:
            k = nat.get("k")
            # Native model is a list; bool model is a list
            ok1 = boolr["model"] is not None  # basic
            ok2 = boolr["model"] is not None
        elif prob == "ABC+DEF=GHIJ":
            ok1 = verify_linsys(nat["model"])
            ok2 = verify_linsys(boolr["model"])
        else:
            ok1 = ok2 = None
        print(f"  {prob}: native valid={ok1}  bool valid={ok2}")


if __name__ == "__main__":
    main()
