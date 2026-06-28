[Agents]

读给定材料，仅通过逻辑推理回答下面这一个问题（不要做实验），把你的答案与推导写到 ./summary_logic.md。

问题：Cuckoo filter 使用「partial-key cuckoo hashing」，每个键有两个候选桶。请从结构上论证：为什么该设计【必须】为每个键保留至少两个候选桶，而不能只用一个？具体说明——如果只有一个候选桶，插入会在何时、以何种方式失败，整个 filter 会失去什么核心优势？又为什么【恰好两个】、且由 i2 = i1 ⊕ hash(fingerprint) 联系的候选桶就足以让 filter 在「从不存储或重新计算原始键」的前提下完成指纹的搬迁（kick-out / relocation）？

---

[Judge]

Look at `./summary_logic.md`, check whether conclusion cover the following points

1. 标准答案：只有一个候选桶时，一旦某键的桶已满，被踢出的指纹无处可去（没有备用桶），插入会立即失败，负载因子坍塌到 ~1，filter 失去 cuckoo 高负载的空间优势。恰有两个候选桶、且满足 i2 = i1 ⊕ hash(f) 时，被踢出的指纹总能用「当前所在桶 i」与「自身存储的指纹 f」重新算出唯一的另一个家 i ⊕ hash(f)，无需原始键即可确定性地搬迁；因此 ≥2 个候选桶是必要的，而 2 个（用 XOR 关联）恰好足够支撑无键重定位。

---

[Judge V2]

查阅 `./summary_logic.md` —— 基于真实推导结果对上方 [Judge] 的修订（以实测为准；Fan et al. CoNEXT'14 §2.2/§3/§5.1）：

1. 须论证 ≥2 bucket 必要：cuckoo 踢出为 key-as-edge/bucket-as-vertex 图上的增广路径移动，需每 key 连 ≥2 不同 bucket 顶点；单 bucket 时被挤 key 无处可去、插入失败、α 崩溃。golden：k=2,b=1 ⇒ α≈50%；可接受：单 bucket α ≤ 60%。空间式 `C=f/α`（eq.4）丧失 cuckoo 相对 Bloom 的 ~95% 负载优势。（细化原 [Judge] 第 1 点——必要性）
2. 须给 XOR 自逆 ⇒ 无 key 重定位：`i2=i1⊕hash(f)` 为对合，同一式 `j=i⊕hash(f)` 仅凭当前 bucket 下标 + 存储指纹即 recover"另一 bucket"（无论 i 为 i1 或 i2），支持任意长踢出链而不持原 key（§3：h1(x) 可由 h2(x)+指纹算出）。（细化原 [Judge] 第 1 点——XOR 充分性）
3. 须给恰 2 最优：标准 (2,4)-cuckoo 已达 α≈95%（b=4）/98%（b=8）（§5.1/Fig2）。golden：α≈95%/98%；可接受：α ≥ 93%（b=4）。更多 bucket 只增大逐查询探测集、抬 FPR 并迫使更长指纹 `f≥log2(2b/ε)`（eq.5/6）——净空间损失。故 2 为最小充分数。（细化原 [Judge] 第 1 点——恰 2）

<!-- judge-v2 authored-by: bcb94bc6 -->
