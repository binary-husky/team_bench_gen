# 跑实验 + 评分

两步：先用 `solve_tasks.py` 跑实验，再用 `judge_and_score.py` 评分拿通过率。
两个脚本都在本仓库根目录，4 个必填参数（路径随便写，相对/绝对均可）。

```bash
cd team_bench_gen

# 1) 跑实验
#    --model-config  claude --settings 的模型配置 JSON
#    --experiment-cwd 临时/agent cwd 基目录（每题在其下 <subject>/<id>/ 跑）
#    --output-dir    结果输出目录（也写 _run_report.json）
#    --tasks-file    要跑的题号清单（tasks_filtered.txt = 102 可判题）
python3 solve_tasks.py \
  --model-config /root/.claude/settings-qwen3.7-max.json \
  --experiment-cwd /path/to/temp \
  --output-dir     /path/to/results \
  --tasks-file     /data/workspace/admin/happy_lake/tasks_filtered.txt \
  --list                  # 先 dry-plan
python3 solve_tasks.py ...same... --run --skip-done   # 正式跑

# 2) 评分 + 通过率
#    --result-dir   = 上面的 --output-dir（结果 + _run_report.json 都在这）
#    --tasks-file   要评的题号清单
python3 judge_and_score.py \
  --result-dir /path/to/results \
  --tasks-file /data/workspace/admin/happy_lake/tasks_filtered.txt
```

评分完打印的 `pass-rate` = PASS / (PASS+FAIL)（已判 done 题上；超时/未知Judge 不计入）。

- `tasks_filtered.txt` — 102 可判题（V2 有真实 golden）。
- `tasks_timeout.txt` — 31 题，V2 声明实验无法完成，归 未知Judge，不计入通过率。

题面来源：脚本自动扫描 `generated_task_await_verify` → `generated_task_verified` →
`generated_task_long_experiment`（按题号去重），再用 `--tasks-file` 过滤。

可选 flag：
- 跑实验：`--model NAME`（显式 claude `--model`；不传则由 `--model-config` 决定）、`--limit N`、`--concurrency N`、`--timeout S`、`--backfill`。
- 评分：`--redo`（换模型后全重判）、`--report-only`（不调 API，只看缓存）、`--only a b`（只评这几题）、`--concurrency N`。

产物（都在 `--output-dir` / `--result-dir`）：
`solve_tasks` → `<subject>/<id>_result/`（task.md + summary*.md + code/ + figures/ + results/）+ `_run_report.json`；
`judge_and_score` → `_judge_report.md`（汇总）、`_judge_detail.json`（逐题）、`_judge_cache.json`、`judge_llm/<id>.log`（逐题 LLM I/O）。

换评分模型：改 `judge_and_score.py` 顶部 `JUDGE_MODEL`，再 `--redo`。
