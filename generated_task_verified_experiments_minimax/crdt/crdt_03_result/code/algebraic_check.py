"""
Algebraic-property check: explicitly verify that for each CRDT,
merge is commutative, associative, and idempotent, while the naive
non-CRDT counter violates at least one of these properties.

Each test draws random payload states from the same generator used in
the main experiment, then checks:
  - commutativity:    merge(a, b) == merge(b, a)
  - associativity:    merge(merge(a, b), c) == merge(a, merge(b, c))
  - idempotence:      merge(a, a) == a

For naive controls we expect at least one of these to fail.
"""

import random
from experiment import (
    GCounter,
    PNCounter,
    LWWRegister,
    ORSet,
    NaiveLastWrite,
    NaiveAccum,
)


def make_random_g_counter(rng, n):
    return GCounter(n, [rng.randint(0, 100) for _ in range(n)])


def make_random_pn_counter(rng, n):
    return PNCounter(n, ([rng.randint(0, 50) for _ in range(n)],
                         [rng.randint(0, 50) for _ in range(n)]))


def make_random_lww(rng):
    return LWWRegister(
        value=rng.choice(["v1", "v2", "v3", "v4"]),
        timestamp=rng.randint(0, 1000),
        replica_id=f"r{rng.randint(0, 4)}",
    )


def make_random_or_set(rng):
    s = set()
    for _ in range(rng.randint(1, 6)):
        s.add((f"e{rng.randint(0, 5)}", f"tag{rng.randrange(1 << 32)}"))
    return ORSet(s)


def make_random_naive_last_write(rng):
    return NaiveLastWrite(rng.randint(-100, 100))


def make_random_naive_accum(rng):
    return NaiveAccum(rng.randint(-100, 100))


def check_properties(name, make_a, make_b, make_c, merge_fn, key_fn, n_trials=200, seed=12345):
    rng = random.Random(seed)
    comm_fail = assoc_fail = idem_fail = 0
    n = 4
    for _ in range(n_trials):
        a = make_a(rng)
        b = make_b(rng)
        c = make_c(rng)

        ab = merge_fn(a, b)
        ba = merge_fn(b, a)
        if key_fn(ab) != key_fn(ba):
            comm_fail += 1

        left = merge_fn(merge_fn(a, b), c)
        right = merge_fn(a, merge_fn(b, c))
        if key_fn(left) != key_fn(right):
            assoc_fail += 1

        aa = merge_fn(a, a)
        if key_fn(aa) != key_fn(a):
            idem_fail += 1

    print(f"{name:>22}: commutative-fails={comm_fail:>3}  "
          f"associative-fails={assoc_fail:>3}  idempotent-fails={idem_fail:>3}  "
          f"(of {n_trials})")


def main():
    seed = 12345

    check_properties("G-Counter",
                     lambda r: make_random_g_counter(r, 4),
                     lambda r: make_random_g_counter(r, 4),
                     lambda r: make_random_g_counter(r, 4),
                     lambda a, b: a.merge(b),
                     lambda x: tuple(x.payload),
                     seed=seed)

    check_properties("PN-Counter",
                     lambda r: make_random_pn_counter(r, 4),
                     lambda r: make_random_pn_counter(r, 4),
                     lambda r: make_random_pn_counter(r, 4),
                     lambda a, b: a.merge(b),
                     lambda x: (tuple(x.P), tuple(x.N)),
                     seed=seed)

    check_properties("LWW-Register",
                     make_random_lww, make_random_lww, make_random_lww,
                     lambda a, b: a.merge(b),
                     lambda x: (x.value, x.timestamp, x.replica_id),
                     seed=seed)

    check_properties("OR-Set",
                     make_random_or_set, make_random_or_set, make_random_or_set,
                     lambda a, b: a.merge(b),
                     lambda x: frozenset(x.payload),
                     seed=seed)

    check_properties("NaiveLastWrite",
                     make_random_naive_last_write,
                     make_random_naive_last_write,
                     make_random_naive_last_write,
                     lambda a, b: a.merge(b),
                     lambda x: x.value,
                     seed=seed)

    check_properties("NaiveAccum",
                     make_random_naive_accum,
                     make_random_naive_accum,
                     make_random_naive_accum,
                     lambda a, b: a.merge(b),
                     lambda x: x.value,
                     seed=seed)


if __name__ == "__main__":
    main()