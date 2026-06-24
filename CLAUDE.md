# team_bench_gen

A repository for **batch generation and archival of verifiable research tasks**. Each
task is a dispatchable spec: an execution Agent reads material / runs experiments /
writes a conclusion, and a Judge Agent looks only at the conclusion file to give a
pass/fail verdict.

The generator **only writes task specs** — it does not run experiments, does not write
conclusions, and does not verify on behalf of downstream agents.

> **Authoritative spec: [`README.md`](./README.md).** When the rules here and the
> README disagree, the README wins. This file is an operational summary + current
> repo snapshot to save future sessions from re-deriving it.

## Directory layout

```
generated_task_await_verify/         # generated, NOT yet verified
generated_task_verified/             # verified tasks (use as extension templates)
generated_task_verified_experiments/ # experiment products of verified tasks (summary/log/code/figures)
```

Convention: one **big_subject** = one subdirectory. All small_subjects under it share
one `{big_subject}_material/` folder. Material is never excessive — add freely.

### Current snapshot (cloned 2026-06-23)

| big_subject | location | tasks |
|---|---|---|
| `cec` | await_verify | `cec_01..13.md` (13) + `cec_material/` |
| `dtlz` | await_verify | `dtlz_01..05.md` + `dtlz_material/` |
| `hpob` | await_verify | `hpob_01..05.md` + `hpob_material/` |
| `jade` | await_verify | `jade_01..05.md` + `jade_material/` |
| `zdt` | await_verify | `zdt_01..05.md` + `zdt_material/` |
| `muon` | **verified** | `muon_01..09.md` (reference template) + full experiment results |

`muon` is the **canonical reference** — model new tasks on its files.

## Task file format (every `*.md` MUST follow this)

```text
[Agents]

读给定材料，做实验，写结论。

<specific experiment task, variables, controls, train/analysis length, metrics, output file>

---

[Judge]

Look at `./summary_<topic>.md`, check whether conclusion cover the following points (≤ 3 points, each clear & verifiable)

1. <verdict point 1>
2. <verdict point 2>
3. <verdict point 3>
```

### Writing rules (these are checked — see self-check below)

- **`[Agents]`** may only explicitly require three things: read the given material, run
  the experiment/analysis, write the conclusion. Do **NOT** instruct the agent to find /
  supplement / register / download material or to search online (spontaneous research by
  the agent is its own behavior, not a task requirement).
- **Material references**: use the generic term "给定材料". Do **NOT** name concrete
  material paths/filenames, in-repo readme files, existing summaries, other research
  records, or another executor's conclusions. (`读给定材料` ✓ · `读某个具体材料文件` ✗)
- **`[Judge]`** holds **result-verdict conditions**, NOT experiment-execution steps.
  Fixed settings (epochs, optimizer, learning rate) go in `[Agents]`, never as Judge
  conditions. ≤ 3 points, each clear and verifiable. Raise IQ to `high-IQ` only when a
  point genuinely requires reading a chart / statistical significance / complex mechanism
  comparison — default is `low-IQ`.
- **Output file**: each task specifies **one** result file, conventionally
  `./summary_<topic>.md`. Judge looks only at that file. Do **NOT** ask the agent to
  modify an existing master report / readme / summary / other research record.

## Skill 1 — new big_subject from a paper

1. Create `generated_task_await_verify/{big_subject}/`. (**Do NOT create brand-new
   big_subjects yet** — confirm first if needed.)
2. Copy **raw, un-reprocessed** material (paper PDF, official repo source, author blog
   post) into `generated_task_await_verify/{big_subject}/{big_subject}_material/`.
3. Write **5** small_subjects: `{big_subject}_{01..05}.md`, difficulty rising slowly.

### 5-task hard constraints

| # | type | requirement |
|---|---|---|
| **01** | logic puzzle (no experiment) | answer via logic only, **source must NOT contain the direct answer**, **exactly one question**, generator provides the **standard answer**, design **1** eval dimension |
| **02–05** | experiment tasks | must run an experiment (see `generated_task_verified/muon/muon_02.md`); generator does NOT run it, only makes a reasonable conjecture, designs **2–3** eval dimensions |

- Tasks must not be too similar to each other.
- Each requires the solver to output a `summary_xxx.md` conclusion.

## Skill 2 — extend from an existing verified small_subject

1. New tasks MUST land in `generated_task_await_verify/{big_subject}/` (not yet verified).
2. If new material is needed, copy into the same `{big_subject}_material/` folder under
   await_verify, following raw-material rules.
3. Naming continues: `{big_subject}_{next-number}.md`.
- Must be verifiable; no two extension tasks too similar; each has an independent research
  question; numbering stays consecutive after adds/deletes.

## Naming summary

| object | path template |
|---|---|
| task md | `{big_subject}/{big_subject}_{number}.md` |
| material folder | `{big_subject}/{big_subject}_material/` |
| result file | `./summary_<topic>.md` |

## Self-check (run after generating or extending any task)

1. Every task has `[Agents]`.
2. Every task has `[Judge]`.
3. `[Agents]` only explicitly requires "read given material, experiment, write conclusion".
4. No explicit instruction to find/supplement/register/download material.
5. No explicit naming of material filenames, existing readme, existing summary, or other
   research-record conclusions.
6. Fixed experiment settings are in `[Agents]`, not written as Judge conditions.
7. Judge conditions check results/conclusions only, ≤ 3 points.
8. Each task has a clear output file.
9. Task numbers are consecutive.
10. Recommended order is consistent after any add/delete.
11. `_01` is a logic puzzle (no experiment, one question, has standard answer, 1 dimension).
12. `_02` onward is an experiment task (2–3 dimensions).

## Operational notes

- This is a **content repo**: no build system, no dependencies, no tests. "Building" =
  writing markdown. Tooling present in the environment: `git`, `node`/`npm`, `python3`.
- Material folders contain PDFs (papers) and `.py`/`.html` reference source — treat as
  read-only inputs unless explicitly asked to add new material.
- Git remote: `origin → https://github.com/binary-husky/team_bench_gen.git`, branch `main`.
  Commit/push only when the user asks.
- `.gitignore` is currently empty.
