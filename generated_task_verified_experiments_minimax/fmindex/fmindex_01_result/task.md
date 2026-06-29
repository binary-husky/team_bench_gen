[Agents]

读给定材料，仅通过逻辑推理回答下面这一个问题（不要做实验），把你的答案与推导写到 ./summary_logic.md。

问题：FM-index 仅用 BWT 的最后一列 L、数组 C（C[c] 为字典序小于 c 的字符个数）以及对 L 的 rank 查询——从不查阅原文——就能通过【从右向左逐字符】扫描模式 P 来计数其出现次数。请解释使该「反向搜索」成立的 LF-mapping 性质：为什么 L 中字符 c 的第 i 次出现，恰好对应 F（第一列）中字符 c 的第 i 次出现？又如何据此在每一步（向已匹配后缀前置字符 c 时）用 rank(c,·) 与 C[c] 正确地收窄行区间？

---

[Judge]

Look at `./summary_logic.md`, check whether conclusion cover the following points

1. 标准答案：BWT 矩阵是 T$ 所有循环旋转排序后的列表，F=排序后的字符、L=最后一列=BWT。LF 性质源于旋转的稳定性：把某行的末字符 L[i] 旋转到最前所得的新行，在「相同 L[i] 字符」的行之间保持相对顺序，故 L 中 c 的第 i 次出现对应 F 中 c 的第 i 次出现；于是 LF(i)=C[L[i]]+rank(L[i],i) 把一行映射到其前驱旋转所在行。反向搜索维护一个行区间 [top,bot)（其旋转后缀已匹配 P 的已处理后缀）；前置字符 c 时，旋转为「c+已匹配后缀」的行恰是 F 中以 c 开头、且后续落在当前区间内的那些行，由 LF 对应关系即新区间 [C[c]+rank(c,top), C[c]+rank(c,bot))。每步两个 rank 查询（每边界一个）；|P| 步后区间大小 = P 的出现次数。全程不需存储原文。

---

[Judge V2]

查阅 `./summary_logic.md` —— 基于真实推导结果对上方 [Judge] 的修订（以实测为准；Ferragina-Manzini FOCS'00）：

1. 须给 LF 性质（旋转稳定性）：同行末字符 c 中，LF 旋转保相对序（两行末字符同为 c ⇒ 字典序由前缀 α 决定，旋转后均以 c 开头仍由 α 决定）⇒ L 中第 i 个 c 映射到 F 中第 i 个 c。（细化原 [Judge] 第 1 点——前半）
2. 须给 LF 公式：`LF(i)=C[L[i]]+rank(L[i],i)`，仅用 L、C、rank（无需原文）将一行映到其前驱旋转的行。（细化原 [Judge] 第 1 点——中段）
3. 须给向后搜索：维护 `[top,bot)`=旋转后缀匹配 P 已处理后缀的行；前置 c 收窄至 `[C[c]+rank(c,top),C[c]+rank(c,bot))`，每步 2 次 rank、|P| 步，终区间大小=P 出现次数，全程不触原文。（细化原 [Judge] 第 1 点——后半）

<!-- judge-v2 authored-by: bcb94bc6 -->
