#!/usr/bin/env bash
# run_glm52.sh — solve the task list with the glm-5.2 model (concurrency 1).
#
# Wraps solve_tasks.py. The model comes entirely from --model-config
# (it sets `model:` and remaps every alias), so no --model flag.
#
# Default config: settings-GLM-5.2-My.json        (direct Zhipu open.bigmodel.cn,
#   model GLM-5.2).
# Alternative:   settings-GLM-5.2-Company.json    (model glm-5.2 lowercase, via
#   the local proxy host.docker.internal:29928). Switch with:
#     MODEL_CONFIG=/root/.claude/settings-GLM-5.2-Company.json ./run_glm52.sh
#
# Usage:
#   ./run_glm52.sh                   # run for real (serial, resumes via --skip-done)
#   ./run_glm52.sh --list            # dry-plan only, no agents spawned
#   ./run_glm52.sh --limit 2         # extra flags pass through to solve_tasks.py
#   CONCURRENCY=2 ./run_glm52.sh     # override the default 1 if you want parallel
#
# Output (results + _run_report.json) -> $OUTPUT_DIR.
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL_CONFIG="${MODEL_CONFIG:-/root/.claude/settings-GLM-5.2-My.json}"
TASKS_FILE="${TASKS_FILE:-/data/workspace/admin/happy_lake/team_bench_gen/tasks_filtered.txt}"
EXPERIMENT_CWD="${EXPERIMENT_CWD:-/data/workspace/admin/run_glm52/.solve_glm52}"
OUTPUT_DIR="${OUTPUT_DIR:-/data/workspace/admin/run_glm52/.solve_glm52_result}"
CONCURRENCY="${CONCURRENCY:-1}"

python3 /data/workspace/admin/happy_lake/team_bench_gen/solve_tasks.py \
  --model-config   "$MODEL_CONFIG" \
  --experiment-cwd "$EXPERIMENT_CWD" \
  --output-dir     "$OUTPUT_DIR" \
  --tasks-file     "$TASKS_FILE" \
  --concurrency    "$CONCURRENCY" \
  --run --skip-done \
  "$@"
