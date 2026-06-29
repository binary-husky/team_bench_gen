# Cuckoo Filter 「partial-key cuckoo hashing」中两个候选桶的必要性论证

> 题目要求仅通过逻辑推理回答。下面所有结论均来自 Fan 等人 2014 年论文 *Cuckoo Filter: Practically Better Than Bloom*（特别是第 3 节「Cuckoo Filter Algorithms」、Algorithm 1–3 以及图 1），并辅以 cuckoo hashing 的经典结构性质。

---

## 1. 总体回答（先给结论，再展开论证）

Cuckoo filter 的 partial-key cuckoo hashing 中，**「每个键有两个候选桶」不是工程上的选择，而是结构上的必然**：

- **至少需要两个候选桶**：cuckoo hashing 的整个动态插入机制（kick-out / relocation）建立在「当两个候选桶都被占满时，可以把其中一个桶里的现有指纹踢出去、并把它放到它的『另一个候选桶』」这一动作上。如果只有一个候选桶，就根本没有「另一个候选桶」可以放置被踢出的指纹，递归搬迁链会被一步截断，插入将以「桶满即失败」的方式提前终止。Filter 同时将失去它相对于普通 Bloom filter / 普通 hash table 的核心优势——**高负载因子下的可写性**（95% 占用下还能继续插入）。
- **恰好两个候选桶已经足够**：因为 i2 = i1 ⊕ hash(fingerprint) 的异或关系具有「对称性」——知道当前桶号 i 和桶里的指纹 f，就能在**不查原始键 x** 的前提下直接算出 f 的另一个候选桶号 i ⊕ hash(f)。这把 cuckoo hashing 的「搬迁」动作完全降级为「只用桶中现有信息」即可完成的局部操作，于是 filter 可以在只存指纹、永远不存/不重新计算原始键 x 的前提下完成 kick-out。

下面给出逐项推导。

---

## 2. 为什么「至少」需要两个候选桶

### 2.1 重新审视 cuckoo hashing 的插入循环

经典 cuckoo hashing（Pagh & Rodler, 2001）的插入伪代码可写成：

```
insert(x):
    if i1 has free slot: place x there; return
    if i2 has free slot: place x there; return
    evict some y currently in i1 or i2
    insert(y) recursively   # y 也只能用 i1(y) 或 i2(y)
```

Algorithm 1 (Insert) 在 paper 里完全对应这一结构：

```
i1 = hash(x); i2 = i1 ⊕ hash(f)
if bucket[i1] or bucket[i2] has empty entry:
    add f; return
for n in 0..MaxNumKicks:
    pick random entry e from bucket[i]
    swap f with e.fingerprint
    i = i ⊕ hash(f)
    if bucket[i] has empty entry: add f; return
return Failure
```

注意 `i = i ⊕ hash(f)` 这一行——这就是搬迁的关键。它要求：当 f 当前所在桶为 i 时，f 还有**另一个**候选桶 `i ⊕ hash(f)` 可以容纳它。如果只有 1 个候选桶，搬迁链路的第一步就不存在。

### 2.2 只有 1 个候选桶时，插入何时、以何种方式失败

把 filter 退化成像普通 hash table 那样——每条记录只有 1 个候选桶——会发生下面几件事：

1. **插入失败模式（mode of failure）**：插入 x 时，f = fingerprint(x)，i1 = hash(x)。如果 bucket[i1] 还有空槽就放进去；否则**立刻失败**，返回 "filter full at this bucket"。没有「试试别的位置」这一说，因为没有别的位置。
2. **失败概率与负载的关系**：桶大小为 b 时，1 个候选桶的 hash table 只能填到约 1/b（甚至更低，因为一旦一个桶被填满就永远无法再向它写入）。整个 filter 的最大可达负载 = 1/b，与 b 无关——这远低于 cuckoo hashing 能达到的 ~95%（b=4 时）。
3. **完全失去 relocate / kick-out 能力**：每个槽一旦被占就永远锁死，任何后续要 hash 到该桶的项都会失败。这等于把 cuckoo filter 退化成普通 bucketized hash table。
4. **失去动态可写性 / 高空间利用率的核心优势**：paper 在 Section 1 列出 cuckoo filter 相对于 Bloom filter 的四大优势，其中「lookup performance 仍能保持（即使占用到 ~95%）」「空间效率优于 space-optimized Bloom filter」都直接来自「能 relocate」。这两个优势在 1 个候选桶的退化结构里全部消失。

### 2.3 结构上的必然性（一句话总结）

cuckoo hashing 的搬迁机制本质上要求：每个被踢出的项都必须**至少有一个『异地』可以搬**。要实现「递归搬迁链不平凡」，搬迁链上每一跳都必须有第二候选位置可跳。这就是「至少 2」的结构理由。

---

## 3. 为什么「恰好」两个就够了——i2 = i1 ⊕ hash(fingerprint) 的妙处

### 3.1 XOR 关系的关键性质：自反 / 对称

定义
- i1 = h1(x) = hash(x)
- i2 = h2(x) = i1 ⊕ hash(f)

设 f 当前在桶 i。XOR 的一个直接推论是：

> 如果 f 的另一候选是 j，则 j = i ⊕ hash(f)。

而且这个关系**完全对称**：
- 从 i1 出发：i1 ⊕ hash(f) = i2 ✓
- 从 i2 出发：i2 ⊕ hash(f) = (i1 ⊕ hash(f)) ⊕ hash(f) = i1 ✓

也就是说，**任意一个候选桶都能推出另一个候选桶，且无需用到原始键 x**。这正是 paper 在 Section 3 标题「partial-key」名字的由来——搬迁时不需要原始 key，只需要桶里的 fingerprint。

### 3.2 为什么这把 kick-out 变成「只用桶内信息」即可完成的操作

在 Algorithm 1 的搬迁循环里，filter 唯一持有的信息是：

- 当前桶号 i
- 当前桶里被选中那个槽的 fingerprint f（来自交换）
- 桶数组本身的读 / 写权限

它没有任何 x 的副本。要把 f 搬到「它的另一个候选位置」，必须能从 (i, f) 算出 j = i ⊕ hash(f)。这正是 i2 = i1 ⊕ hash(f) 提供的功能。

反过来说，**如果 i1 和 i2 之间的关系不是这种 XOR 形式**——比如 h2 是一个真正独立于 f 的 hash，那么搬迁一个被踢出的 f 时，filter 不知道 f 的 h2(f) 是多少（因为 f 来自别的 x、filter 并不持有那个 x），搬迁就无法继续。所以 XOR 不是任意一个 hash 函数都行——它必须满足「由 (当前桶号, 当前 fingerprint) 唯一确定另一个候选桶号」这一代数性质。

### 3.3 为什么 2 个候选桶足够（为什么不必更多）

直觉上：搬迁链路每一跳都需要「被踢出项的另一个候选位置」。当 i2 = i1 ⊕ hash(f) 时，**每一跳的两个候选位置是同一对 {i1, i2}**，所以搬迁链永远在这两个桶之间往复。这已经能产生任意长的搬迁序列，从而打破「桶一旦填满就锁死」的死锁——这正是 cuckoo hashing 在 (b=2, 两 hash 函数) 时能达到 ~84%、(b=4) 时能达到 ~95% 的根本原因（见 paper Section 4 的 lower bound 与图 2）。

如果有 ≥3 个候选桶：
- 要让 filter 在「只看 fingerprint」的前提下也能搬迁，必须把 (key, fingerprint) 三元组关系编码进桶——而 fingerprint 本身信息量很小（只有 f 位），无法承载多桶的拓扑结构。paper Section 4 给出下界 4^bf = Ω(n/b)，所以 fingerprint 大小必须随 n 增长，根本无法在不存原键的前提下支持更多候选桶。
- lookup 成本随候选桶数线性增加：每多一个候选桶，Algorithm 2 就要多读一个桶，缓存未命中风险倍增。paper Table 2 中 cuckoo filter 的 lookup 始终是「2 次 cache miss」，多候选桶会破坏这一点。
- 在 b=4、两 hash 函数的设置下，paper 图 2 已经显示可达 ~95.5% 占用率，与理论极限几乎持平——再加候选桶带来的边际收益非常有限，反而会显著增加失败概率的 lower bound。

所以从「能用最少的存储（fingerprint）+ 最少的查询成本（两个桶）」完成「无 key 的搬迁」这个角度看，**恰好 2 个候选桶是结构和性能上的最优解**。

---

## 4. 把上面三节串成一张图（搬迁一帧的画面）

```
插入 x：
  f = fingerprint(x)
  i1 = hash(x),  i2 = i1 ⊕ hash(f)
  ────────────────────────────────────────────────
  看 bucket[i1] 和 bucket[i2]：
    · 任一有空 → 放入 f
    · 都满    → 随机选 i ∈ {i1,i2} 的某个 entry e
               交换 f 与 e.f
               更新 i ← i ⊕ hash(f)         ← 这里「不查 x」
               重复
  · 超过 MaxNumKicks → 视为表满，返回 Failure
```

关键点：

- 第 1 步和最后一步不需要「另一候选位置」也能完成；
- 搬迁那一行的存在**预设**了两个候选桶的存在，并且它们之间的可逆关系允许仅凭 (i, f) 算出 j；
- 如果只有 1 个候选桶，搬迁行无意义；如果候选桶多于 2 个，搬迁行无法仅凭 f 计算（除非多存信息），且查询更慢。

---

## 5. 一句话总结

- **为什么 ≥2**：cuckoo hashing 的动态搬迁要求「每个被踢出的项都还有『另一个候选位置』可以搬」；没有第 2 个候选桶，搬迁链第一步就死，filter 退化为固定槽位 hash table，丧失高占用下的可写性（95%+ 占用）和对 Bloom filter 的空间/性能优势。
- **为什么 =2 且恰好由 XOR 联系**：XOR 关系 `i2 = i1 ⊕ hash(f)` 自反对称，使得「被踢出的 f 在新桶号 i 时，其另一候选号是 i ⊕ hash(f)」——这条计算只用桶内的 (i, f) 两个量，**完全不需要原始键 x**；这就让 kick-out 可以在「不存 key、不重算 key」的 partial-key 假设下递归进行。Lookup 只需读 2 个桶（最优 cache 行为），而两 hash 函数的 cuckoo hashing 配合 b≥4 的桶已经能逼近理论负载上界，因此再多候选桶在结构上没有收益、在代价上得不偿失。
