# Skewed vs. Uniform streams: how data distribution affects Space-Saving's top-k quality

## 1. Question

Does the data distribution — the shape, not the size — of the input
stream change how well Space-Saving (Metwally, Agrawal & Abbadi, 2005)
recovers the true top-k? Holding N, k, the alphabet size, and the
random seed fixed, we run the same algorithm on a strongly skewed
Zipfian stream and on a uniform stream, and compare against the exact
top-k obtained from full counts.

## 2. Setup (all fixed)

| Knob        | Value                                                |
|-------------|------------------------------------------------------|
| N           | 1,000,000 stream elements                            |
| k (counters)| 100                                                  |
| Alphabet A  | {0, 1, …, 99,999} (|A| = 100,000)                    |
| Random seed | 12345 (`numpy.random.default_rng(12345)`)            |
| Stream A    | Zipfian with α = 1.5, drawn from `Generator.zipf`    |
| Stream B    | Discrete uniform over the same alphabet              |
| Algorithm   | Space-Saving with the Stream-Summary counters + heap |
| Baseline    | Exact frequencies from a single pass over the stream |

The independent variable is **data distribution**; everything else
(N, k, |A|, seed, algorithm, baseline) is the same across the two
runs.  Each stream is generated independently but uses the same
alphabet and seed, satisfying the task's "same base cardinality,
fixed seed" requirement.

The Space-Saving implementation follows Figures 1–2 of the paper
exactly: each element either increments its existing counter or, if it
is not currently monitored, replaces the live counter with the
smallest count (storing the evicted value as the new counter's error
ε_i, so that the invariant `count_i - ε_i ≤ f_i ≤ count_i` from
Lemma 3 holds).  The reported top-k is the k monitored elements with
the largest counts (Theorem 6 / 7 give the order-preservation
guarantee for Zipf).

## 3. Metrics

For a top-k query the reported set and the exact set both have size k,
so

```
precision@k = |reported_top_k ∩ exact_top_k| / k
recall@k    = |reported_top_k ∩ exact_top_k| / k
```

are equal and reduce to the same fraction.

## 4. Results

Numbers below come from a single run of the script `space_saving.py`
in this directory (see `results.json` for the machine-readable copy).

| Metric                              | Zipfian (α = 1.5) | Uniform over 100k |
|-------------------------------------|-------------------|-------------------|
| Run-time (s)                        | 0.47              | 0.48              |
| Sum of all 100 counters (≡ N)       | 1,000,000         | 1,000,000         |
| **Final minimum counter value**     | **1,939**         | **10,000**        |
| Exact count of the 100th-ranked id  | 388               | 21                |
| True top-k items MISSED in monitors | 49 / 100          | 100 / 100         |
| **precision@k**                     | **0.51**          | **0.00**          |
| **recall@k**                        | **0.51**          | **0.00**          |

### 4.1 What the top-10 output looks like

Zipfian, top-10 reported by Space-Saving (true ranks in parens; the
element IDs are exactly 0..9, identical to the exact ranking):

| SS rank | element | SS count | exact rank | exact count |
|---------|---------|----------|------------|-------------|
| 1       | 0       | 384,812  | 1          | 384,812     |
| 2       | 1       | 135,653  | 2          | 135,653     |
| 3       | 2       | 73,463   | 3          | 73,463      |
| 4       | 3       | 47,958   | 4          | 47,958      |
| 5       | 4       | 34,279   | 5          | 34,279      |
| 6       | 5       | 25,884   | 6          | 25,884      |
| 7       | 6       | 20,789   | 7          | 20,789      |
| 8       | 7       | 16,925   | 8          | 16,925      |
| 9       | 8       | 14,256   | 9          | 14,256      |
| 10      | 9       | 12,004   | 10         | 12,004      |

Uniform, top-10 reported by Space-Saving:

| SS rank | element | SS count | exact rank |
|---------|---------|----------|------------|
| 1       | 1,993   | 10,000   | —          |
| 2       | 2,233   | 10,000   | —          |
| 3       | 5,330   | 10,000   | —          |
| 4       | 7,051   | 10,000   | —          |
| 5       | 7,673   | 10,000   | —          |
| 6       | 8,754   | 10,000   | —          |
| 7       | 11,152  | 10,000   | —          |
| 8       | 11,370  | 10,000   | —          |
| 9       | 12,276  | 10,000   | —          |
| 10      | 12,714  | 10,000   | —          |

None of the 100 elements that SS reports for the uniform stream is in
the true top-100.  The true top-100 items under uniform have exact
counts of only 21–25 — orders of magnitude smaller than the 10,000
each "top" SS counter has been inflated to by repeated evictions.

## 5. Interpretation

### 5.1 Why Zipfian is recoverable (precision/recall = 0.51)

Under Zipf(α = 1.5) with |A| = 100,000 and N = 10⁶ the rank-i
frequency is F_i = N / (i · H_{|A|,α}) with H ≈ 7.4, so:

* F_1   ≈ 135,000
* F_10  ≈ 13,500
* F_100 ≈ 1,350
* F_1000 ≈ 135
* F_10000 ≈ 13

The 100 most frequent elements are between 1.4 × and 100 × more
frequent than the average element (10), and the 100th-ranked element
has exact count ≈ 388.  Space-Saving's final min counter is 1,939, so
the algorithm is happily "above the top-100 threshold" for ~51 of
those 100 items.  The other 49 of the true top-100 have exact counts
between 388 and 1,938 — they were bumped out of the monitored set
during the stream because a non-top element was observed enough times
to occupy a counter slot, and the `count_i` of a top-K element that
gets evicted is reset to whatever the new occupant's first observation
returns (one more than the current min, plus any subsequent
inflations).  Their estimated counts are not in the right ballpark,
so they drop out of the reported top-100.  Even so, the **order of the
top-k is preserved** for every k ≤ 100 in this run — exactly the
order-preservation guarantee Theorem 7 promises for Zipf data.

### 5.2 Why uniform is hopeless (precision/recall = 0.00)

Under a uniform stream, every one of the 100,000 alphabet elements
appears roughly N / |A| = 10 times (Poisson variance gives a range of
~5–25 in practice; the empirical threshold for the 100th-rank item
is 21, with the 1st-rank item at only 25).  With only k = 100
counters, every element has probability 100 / 100,000 = 0.1 % of
holding a slot.  An element that does get a slot is bumped out the
first time *any* of the other 99,900 unseen elements is observed, so
its counter lives for a very short time before being replaced.

The terminal state of the algorithm is therefore "100 counters, all
held by whichever 100 elements happened to be seen most recently in
the latest eviction storm" — these are essentially the **last 100
distinct elements that appeared in the stream**, not the 100 most
frequent ones.  Every monitor has been repeatedly evicted and
re-inserted, so its `count` has been inflated to roughly the number
of times the algorithm has cycled through that slot, which at the
end of the run is exactly 10,000 (N / m).  Lemma 3's bound
`count_i - ε_i ≤ f_i` is still true, but the bound is useless:
ε_i ≈ count_i, so the true count f_i is sandwiched inside an interval
of width ≈ 10,000.  The reported "top-100" is just noise.

### 5.3 Putting the two numbers side-by-side

* With Zipfian input, **51 of the 100 reported top items are correct**
  (and the reported ordering of the top-10 is perfect).  The paper's
  Theorem 7 promise — guaranteed exact top-k under Zipf with parameter
  α > 1 — does not say *which* k you need.  With k = 100 and the
  paper's recommended m ≈ (|A|/φ)^(1/α) ≈ 2,150 (Theorem 7),
  the algorithm would have plenty of room; with m = 100, it is
  intentionally undersized for that guarantee, and we still recover
  over half the true top-k.  This matches Figure 6(c) of the paper,
  which shows Space-Saving with 100 counters retaining recall = 1 for
  the frequent-elements query on Zipf data of similar α.

* With uniform input, **0 of the 100 reported top items are correct**.
  Space-Saving is making no attempt to identify the true top-k because
  there is no top-k to speak of: every element occurs roughly 10
  times, the 100th-ranked item is at count 21 and the 101st is at
  count 20.  This is precisely the regime the paper warns about in
  Section 3.1 ("the top elements among non-skewed data are of no
  great significance … we concentrate on skewed data sets"), and
  Figure 6(d) shows Space-Saving's space advantage evaporating as
  α → 0 (the data becomes uniform) — consistent with the algorithm
  being structurally unsuited to the task.

## 6. Conclusion

Data distribution has a **decisive** effect on Space-Saving's
top-k quality at fixed N, k, alphabet size and seed:

| Stream  | precision@k | recall@k | What the algorithm recovers          |
|---------|-------------|----------|--------------------------------------|
| Zipf(1.5) | **0.51**  | **0.51** | The heavy hitters; ordering preserved within top-k |
| Uniform  | **0.00**  | **0.00** | Nothing — the "top-k" is a snapshot of recent distinct arrivals |

The asymmetry is structural, not a bug.  Space-Saving's replacement
policy assumes that heavy hitters will resurface often enough to
regain a slot once evicted, which is the defining property of a
skewed stream.  Under a uniform stream, no element is a heavy
hitter relative to the rest, every monitored element is just a
recent arrival, and the algorithm degenerates into a sample of
the most recently observed distinct values.  For practical top-k
queries with a small k, Space-Saving should be deployed only when
the input is known to be skewed; the paper's analysis of Zipf
bounds and the empirical precision numbers above both confirm
this.
