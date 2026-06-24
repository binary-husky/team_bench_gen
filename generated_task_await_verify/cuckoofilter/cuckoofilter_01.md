[Agents]

读给定材料，仅通过逻辑推理回答下面这一个问题（不要做实验），把你的答案与推导写到 ./summary_logic.md。

问题：Cuckoo filter 使用「partial-key cuckoo hashing」，每个键有两个候选桶。请从结构上论证：为什么该设计【必须】为每个键保留至少两个候选桶，而不能只用一个？具体说明——如果只有一个候选桶，插入会在何时、以何种方式失败，整个 filter 会失去什么核心优势？又为什么【恰好两个】、且由 i2 = i1 ⊕ hash(fingerprint) 联系的候选桶就足以让 filter 在「从不存储或重新计算原始键」的前提下完成指纹的搬迁（kick-out / relocation）？

---

[Judge]

Look at `./summary_logic.md`, check whether conclusion cover the following points

1. 标准答案：只有一个候选桶时，一旦某键的桶已满，被踢出的指纹无处可去（没有备用桶），插入会立即失败，负载因子坍塌到 ~1，filter 失去 cuckoo 高负载的空间优势。恰有两个候选桶、且满足 i2 = i1 ⊕ hash(f) 时，被踢出的指纹总能用「当前所在桶 i」与「自身存储的指纹 f」重新算出唯一的另一个家 i ⊕ hash(f)，无需原始键即可确定性地搬迁；因此 ≥2 个候选桶是必要的，而 2 个（用 XOR 关联）恰好足够支撑无键重定位。
