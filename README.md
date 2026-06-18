# team_bench_gen

一个**可验证研究课题**的批量生成与沉淀仓库。每个课题都是一份可直接派发给执行 Agent 和 Judge Agent 的任务单：执行 Agent 读材料 / 做实验 / 写结论，Judge Agent 只看结论文件给通过/不通过。

生成者**只负责拟写课题**，不运行实验、不写实验结论、不替后续 Agent 做验证。

---

## 仓库结构

```
team_bench_gen/
├── generated_task_await_verify/         # 已生成、尚未通过验证的课题
│   ├── cec/      cec_{01..08}.md  + cec_material/
│   ├── hpob/     hpob_{01..05}.md + hpob_material/
│   └── {new_big_subject}/               # 新大课题落到这里
│
├── generated_task_verified/             # 已通过验证的课题（可作为拓展模板）
│   ├── muon/     muon_{01..09}.md + muon_material/
│   └── {new_big_subject}/
│
└── generated_task_verified_experiments/ # 已验证课题的实验产物（summary、log 等）
    ├── muon/
    └── {new_big_subject}/
```

**目录约定**：一个大课题 (big_subject) 一个子目录；该大课题下所有小课题共享同一个 material 目录，material 不嫌多。

---

## 课题文件格式

每个 `*.md` 必须使用以下结构：

```text
[Agents]

读给定材料，做实验，写结论。

<具体实验任务、变量、对照组、训练/分析长度、记录指标、输出文件>

---

[Judge (IQ requirement: low-IQ | high-IQ)]

Look at `./summary_<topic>.md`, check whether conclusion cover the following points (最多不超过 3 点，每点都必须清晰、可验证)

1. <结果判定点 1>
2. <结果判定点 2>
3. <结果判定点 3>
```

### `[Agents]` 写法

`[Agents]` 是给执行 Agent 的任务布置，只显式要求三件事：

1. 读给定材料。
2. 做实验或分析。
3. 写结论。

不要在任务文本里显式要求 Agent 查找资料、补充资料、联网搜索或登记材料。如果 Agent 自发查资料，那是 Agent 自己的行为，不应写成任务要求。

### 给定材料写法

使用"给定材料"这个统称，**不要**显式提及材料的具体路径、文件名、项目内已有说明文件、既有总结、其他研究记录或其他执行者的结论。

| ✅ 推荐 | ❌ 不推荐 |
|---|---|
| `读给定材料` | `读某个具体材料文件` |
|  | `参考项目内已有说明文件` |
|  | `根据已有总结` |
|  | `查看其他研究记录中的结论` |

### `[Judge]` 写法

`[Judge]` 是**研究结果判定条件**，不是实验执行说明。

- 固定实验设置（epoch 数、优化器、学习率等）写在 `[Agents]`，不要写成 Judge 判定条件。
- Judge 条件只检查研究结果和结论，**最多 3 点**，每点都必须清晰、可验证。
- 如果判定需要读图、理解统计显著性、比较复杂机制解释，可以提高 IQ requirement，但必须有必要性；默认 `low-IQ`。

### 输出文件写法

每个课题指定**一个**结果文件，通常命名为 `./summary_<topic>.md`。Judge 只查看该文件进行判定。**不要**要求 Agent 修改已有总报告、已有说明文件、已有总结或其他已有研究记录。

---

## Skill 1：从论文产生新大课题

从一个论文 PDF 抽取一个大课题 (big_subject)，围绕它生成 **5 个**可验证小课题 (small_subject)，复杂度和难度缓慢提升。

**示例参考论文**：<https://arxiv.org/pdf/2106.06257>

### 流程

1. 在 `generated_task_await_verify/{big_subject}/` 下新建子目录（暂时**不允许**创建全新大课题——如需新建请先确认）。
2. 把原始材料复制到 `generated_task_await_verify/{big_subject}/{big_subject}_material/`。**材料必须是直接从互联网获取的、未二次加工的原始材料**（论文 PDF、官方仓库源码、作者博客原文等）。
3. 写 5 个小课题：`{big_subject}_{01..05}.md`，遵循上面的格式。

### 5 个小课题的硬约束

| 编号 | 类型 | 要求 |
|---|---|---|
| **01** | 逻辑推理题（无实验） | 通过逻辑推理得到答案，**原文不得存在直接答案**；**只能有一个问题**；生成者必须给出**标准答案**，设计 **1** 个评价维度 |
| **02–05** | 实验题 | 需要做实验得出结论（参考 `generated_task_verified/muon/muon_02.md`）；生成者不亲自做实验，只做合理猜想，设计 **2–3** 个评价维度 |

通用约束：
- 不得创建过于相似的小课题。
- 每个课题都要求解题者输出一个 `summary_xxx.md` 作为结论。

---

## Skill 2：从已有小课题拓展更多小课题

从一个**已验证**的小课题出发，派生出更多同主题、不同角度的小课题。

**示例**：

```
原始：generated_task_verified/muon/muon_02.md
拓展：generated_task_verified/muon/muon_03.md
      generated_task_verified/muon/muon_04.md
      generated_task_verified/muon/muon_05.md
      generated_task_verified/muon/muon_06.md
```

### 流程

1. 拓展出的新课题**必须**落到 `generated_task_await_verify/{big_subject}/`（因为没验证）。
2. 如果需要新材料，复制到 `generated_task_await_verify/{big_subject}/{big_subject}_material/`，沿用原始材料规则。
3. 命名沿用 `{big_subject}_{下一个编号}.md`。

### 课题选择原则

- 课题必须**可验证**——Judge 能基于结论文件给出明确的通过/不通过。
- 拓展课题之间不得过于相似；每个新课题都应有独立的研究问题。
- 编号连续，新增/删除后保持编号一致。

---

## 命名规则汇总

| 对象 | 路径模板 |
|---|---|
| 课题 md | `{big_subject}/{big_subject}_{编号}.md` |
| 材料文件夹 | `{big_subject}/{big_subject}_material/` |
| 结果文件 | `./summary_<topic>.md` |

---

## 自检清单

生成或拓展任务单后，检查以下事项：

1. 每个课题都有 `[Agents]`。
2. 每个课题都有 `[Judge (IQ requirement: ...)]`。
3. `[Agents]` 中只显式要求"读给定材料，做实验，写结论"。
4. 没有显式要求 Agent 查找、补充、登记或下载材料。
5. 没有显式提及材料文件名、已有说明文件、既有总结或其他研究记录结论。
6. 固定实验设置写在 `[Agents]`，没有写成 Judge 判定条件。
7. Judge 条件只检查研究结果和结论，最多 3 点。
8. 每个课题都有明确输出文件。
9. 课题编号连续。
10. 推荐顺序与删除或新增后的编号一致。
11. `_01` 是逻辑推理题（无实验、单问题、有标准答案、1 个评价维度）。
12. `_02` 起是实验题（2–3 个评价维度）。
