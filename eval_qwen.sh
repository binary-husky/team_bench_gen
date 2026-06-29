#!/usr/bin/env bash
# eval_qwen.sh — judge + score the results produced by run_qwen.sh.
#
# Wraps judge_and_score.py. --result-dir defaults to run_qwen.sh's OUTPUT_DIR,
# so it evals the qwen result by default; override RESULT_DIR to eval any prior run.
#
# Usage:
#   ./eval_qwen.sh                   # judge all done tasks (cached; resumable)
#   ./eval_qwen.sh --redo            # re-judge, ignoring cache
#   ./eval_qwen.sh --report-only     # no API calls; rebuild report from cache
#   ./eval_qwen.sh --only tsne_01    # judge specific tasks
#   RESULT_DIR=/path/to/other_results ./eval_qwen.sh   # eval a different run
#
# Writes _judge_report.md / _judge_detail.json / _judge_cache.json / judge_llm/
# into $RESULT_DIR. Prints pass-rate + mean score at the end.
set -euo pipefail
cd "$(dirname "$0")"

RESULT_DIR="${RESULT_DIR:-/data/workspace/admin/happy_lake/team_bench_gen/generated_task_verified_experiments_qwen}"
TASKS_FILE="${TASKS_FILE:-/data/workspace/admin/happy_lake/tasks_filtered.txt}"
CONCURRENCY="${CONCURRENCY:-4}"

python3 judge_and_score.py \
  --result-dir  "$RESULT_DIR" \
  --tasks-file  "$TASKS_FILE" \
  --concurrency "$CONCURRENCY" \
  "$@"
