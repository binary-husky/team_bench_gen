#!/usr/bin/env bash
# run_qwen.sh — solve the task list with the qwen3.7-max model.
#
# Wraps solve_tasks.py. The model comes entirely from --model-config
# (it sets `model: qwen3.7-max` and remaps every alias), so no --model flag.
#
# Usage:
#   ./run_qwen.sh                    # run for real (resumes via --skip-done)
#   ./run_qwen.sh --list             # dry-plan only, no agents spawned
#   CONCURRENCY=4 ./run_qwen.sh      # parallel workers (default 1 = serial)
#   ./run_qwen.sh --limit 2          # extra flags pass through to solve_tasks.py
#   OUTPUT_DIR=/elsewhere ./run_qwen.sh   # override any default via env
#
# Output (results + _run_report.json) -> $OUTPUT_DIR  (the eval script reads it).
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_CONFIG="${MODEL_CONFIG:-/root/.claude/settings-Qwen3.6-35B-A3B.json}"
TASKS_FILE="${TASKS_FILE:-/data/workspace/admin/happy_lake/team_bench_gen/tasks_filtered.txt}"
EXPERIMENT_CWD="${EXPERIMENT_CWD:-/data/workspace/admin/happy_lake/.solve_qwen35B}"
OUTPUT_DIR="${OUTPUT_DIR:-/data/workspace/admin/happy_lake/.solve_qwen35B_result}"
CONCURRENCY="${CONCURRENCY:-3}"

python3 /data/workspace/admin/happy_lake/team_bench_gen/solve_tasks.py \
  --model-config   "$MODEL_CONFIG" \
  --experiment-cwd "$EXPERIMENT_CWD" \
  --output-dir     "$OUTPUT_DIR" \
  --tasks-file     "$TASKS_FILE" \
  --concurrency    "$CONCURRENCY" \
  --run --skip-done \
  "$@"
