#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-/root/muon_code}"
OUT="${OUT:-/root/muon_results/robustness_10ep}"
LOGDIR="${LOGDIR:-/root/muon_logs/robustness_10ep}"
DATA="${DATA:-/tmp/cifar10_smoke}"
EPOCHS="${EPOCHS:-10}"
BS="${BS:-256}"
NW="${NW:-2}"

mkdir -p "$OUT" "$LOGDIR"
cd "$ROOT"

runs=()
for opt in muon sgd adamw; do
  for n in 5000 10000 25000 50000; do
    runs+=("$opt|small_$n|--small-data $n")
  done
  for p in 0.0 0.1 0.2 0.4; do
    runs+=("$opt|noise_$p|--label-noise $p")
  done
  for r in 10 50; do
    runs+=("$opt|longtail_$r|--long-tail $r")
  done
done

batch_size="${BATCH_SIZE:-8}"
total="${#runs[@]}"
for ((start=0; start<total; start+=batch_size)); do
  end=$((start + batch_size))
  if (( end > total )); then end=$total; fi
  echo "[batch] runs $start..$((end-1)) of $total"
  pids=()
  for ((i=start; i<end; i++)); do
    IFS='|' read -r opt tag extra <<<"${runs[$i]}"
    gpu=$(( (i - start) % batch_size ))
    log="$LOGDIR/${opt}_${tag}.log"
    echo "[launch] gpu=$gpu opt=$opt tag=$tag extra=$extra"
    CUDA_VISIBLE_DEVICES="$gpu" python3 robust_train.py \
      --optimizer "$opt" \
      --epochs "$EPOCHS" \
      --batch-size "$BS" \
      --data-dir "$DATA" \
      --out "$OUT" \
      --num-workers "$NW" \
      --milestones 7 9 \
      $extra \
      >"$log" 2>&1 &
    pids+=("$!")
  done
  fail=0
  for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
      fail=1
    fi
  done
  if (( fail != 0 )); then
    echo "[batch] failure in runs $start..$((end-1)); see $LOGDIR" >&2
    exit 1
  fi
  echo "[batch] done $start..$((end-1))"
done

echo "[done] all $total robustness 10ep runs finished"
