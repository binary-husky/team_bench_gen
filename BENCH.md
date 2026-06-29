# MiniMax-M3 跑实验 + GLM 评分

两步：先跑 `tasks_filtered.txt`（102 可判题），再 GLM 评分拿通过率。

```bash
cd /data/workspace/admin/happy_lake

# 1) 跑实验（MiniMax-M3）。先 dry-plan，再正式跑
#    --stage-dir   临时目录 = agent 的 cwd（默认 .verify_judge_minimax）
#    --results-dir 结果输出目录（默认 generated_task_verified_experiments_minimax）
python3 run_verify_judge_minimax.py --tasks-file tasks_filtered.txt \
  --stage-dir /path/to/temp --results-dir /path/to/results --list
python3 run_verify_judge_minimax.py --tasks-file tasks_filtered.txt \
  --stage-dir /path/to/temp --results-dir /path/to/results --run --skip-done

# 2) GLM 评分 + 通过率（默认只评 filtered 集）
python3 judge_minimax_glm.py
```

评分完打印的 `pass-rate` 即通过率 = PASS / (PASS+FAIL)（已判 done 题上；超时/未知Judge 不计入）。

- `tasks_filtered.txt` — 102 可判题（V2 有真实 golden）。
- `tasks_timeout.txt` — 31 题，V2 声明实验无法完成，归 未知Judge，不计入通过率。

常用 flag：
- 跑实验：`--stage-dir DIR`（临时/agent cwd）、`--results-dir DIR`（结果输出）、`--limit N`（试跑）、`--concurrency N`、`--backfill`（只收割产物不跑 agent）。
- 评分：`--redo`（换模型后全重判）、`--report-only`（不调 API，只看缓存结果）、`--no-filter`（评全 133）。

产物：`.verify_judge_minimax/_glm_judge_report.md`（汇总）、`_glm_judge_detail.json`（逐题）、`temp/judge_llm/<task_id>.log`（逐题 LLM I/O）。

换评分模型：改 `judge_minimax_glm.py` 顶部 `JUDGE_MODEL`，再 `--redo`。
