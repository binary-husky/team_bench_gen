#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
solve_tasks.py — Phase-2 EXECUTION orchestrator (model-agnostic).

Runs a Claude Code agent (in its own tmux window, configured by a model-config
JSON) on each task in a task list, and harvests the measured results into an
output directory. It is the merged successor of run_verify_judge_glm.py /
run_verify_judge_minimax.py — what used to be hardcoded per lane (settings file,
model, temp cwd, results dir, task set) is now four REQUIRED CLI arguments.

Required arguments:
  --model-config    claude --settings JSON, e.g. /root/.claude/settings-qwen3.7-max.json
  --experiment-cwd  base temp/staging dir; each task runs in
                    <experiment-cwd>/<subject>/<subject>_<NN>/  (the agent cwd)
  --output-dir      where per-task results + _run_report.json are written
  --tasks-file      file of task IDs to run (one per line; '#' comments ok)

Optional: --model (claude --model name; default: omit, let --model-config decide),
  --list / --run, --subjects, --limit, --concurrency, --timeout, --skip-done, --backfill.

Task specs are discovered by scanning, in order:
  generated_task_await_verify/ , generated_task_verified/ , generated_task_long_experiment/
(under this repo), then filtered to the IDs in --tasks-file.

Per task the script: stages a judge-stripped task.md + material copy into the
per-task cwd, spawns the agent, waits for a __DONE__ sentinel / timeout / dead
window, then copies the full original spec + all produced artifacts into
<output-dir>/<subject>/<subject>_<NN>_result/  (task.md + summary*.md + code/ +
figures/ + results/).
"""

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# --------------------------------------------------------------------------- #
# Location (derived from this file so the script runs from any cwd)
# --------------------------------------------------------------------------- #
WORKSPACE = Path(__file__).resolve().parent.parent          # .../happy_lake
REPO      = Path(__file__).resolve().parent                  # .../team_bench_gen
CANDIDATE_TASK_DIRS = [
    REPO / "generated_task_await_verify",
    REPO / "generated_task_verified",
    REPO / "generated_task_long_experiment",
]

# --------------------------------------------------------------------------- #
# Agent harness timing knobs
# --------------------------------------------------------------------------- #
AGENT_BOOT_SECONDS = 8      # wait for the claude REPL to come up before pasting
POLL_INTERVAL      = 10     # seconds between completion checks
TASK_TIMEOUT       = 2400   # per-task wall-clock cap (40 min; specs budget <30)
DONE_SENTINEL      = "__DONE__"

# Heavy optimization-benchmark reproductions — likely infeasible under the
# CPU/<30-min bar. Attempt ONCE with a SHORT budget, skip on timeout (no retry).
PRE_EXISTING = {"cec", "dtlz", "hpob", "jade", "zdt"}
PRE_TIMEOUT  = 300          # 5-min single attempt for pre-existing subjects

# Assigned in main() from the required CLI args (referenced as globals below):
STAGE_ROOT       = None     # <experiment-cwd>   (per-task agent cwd base)
EXPERIMENTS_DIR  = None     # <output-dir>       (results + run report)
CLAUDE_SETTINGS  = None     # <model-config>     (claude --settings path)
MODEL            = None     # <model>            (claude --model name, or None)
TMUX_SESSION     = "solve_tasks"
SKIPPED_FILE     = None
SKIPLIST_FILE    = None
SKIPLIST         = set()

# Per-task name uniqueness (tmux window + buffer names share a global counter)
_seq_lock = threading.Lock()
_seq = 0


def next_seq():
    global _seq
    with _seq_lock:
        _seq += 1
        return _seq


# --------------------------------------------------------------------------- #
# Low-level tmux / shell helpers
# --------------------------------------------------------------------------- #
def run(cmd, check=False, capture=True, timeout=None):
    return subprocess.run(
        cmd, check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True, timeout=timeout,
    )


def tmux(*args, check=False, timeout=None):
    return run(["tmux", *args], check=check, capture=True, timeout=timeout)


def tmux_has_session(name):
    r = tmux("has-session", "-t", name)
    return r.returncode == 0


def ensure_session():
    if not tmux_has_session(TMUX_SESSION):
        tmux("new-session", "-d", "-s", TMUX_SESSION,
             "-c", str(WORKSPACE), check=True)
        log(f"[session] created tmux session '{TMUX_SESSION}' (cwd={WORKSPACE})")
    return TMUX_SESSION


def sanitize_window_name(name):
    name = name.replace(".", "_").replace(":", "_")
    return name[:40]


def derive_session_name(output_dir, model_config):
    """A unique-per-run tmux session name so concurrent lanes never clash."""
    stem = model_config.stem
    if stem.startswith("settings-"):
        stem = stem[len("settings-"):]
    raw = f"solve_{output_dir.name}_{stem}"
    return raw.replace(".", "_").replace(":", "_")[:60]


def capture_pane(target, lines=220):
    r = tmux("capture-pane", "-p", "-t", target, "-S", f"-{lines}")
    return r.stdout if r.returncode == 0 else ""


def pane_alive(target):
    sess = target.split(":")[0]
    r = tmux("list-windows", "-t", sess, "-F", "#{window_name}")
    if r.returncode != 0:
        return False
    return target.split(":")[-1] in r.stdout.splitlines()


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #
_log_lock = threading.Lock()
_start_ts = time.time()


def log(msg):
    ts = time.strftime("%H:%M:%S")
    rel = time.time() - _start_ts
    line = f"[{ts} +{rel:7.1f}s] {msg}"
    with _log_lock:
        print(line, flush=True)


# --------------------------------------------------------------------------- #
# Task discovery (union of candidate source dirs, deduped by task_id)
# --------------------------------------------------------------------------- #
def discover_tasks():
    tasks = []
    seen = set()
    for base in CANDIDATE_TASK_DIRS:
        if not base.is_dir():
            continue
        for subj_dir in sorted(base.iterdir()):
            if not subj_dir.is_dir():
                continue
            subject = subj_dir.name
            for md in sorted(subj_dir.glob(f"{subject}_*.md")):
                m = re.match(rf"^{re.escape(subject)}_(\d+)\.md$", md.name)
                if not m:
                    continue
                tid = f"{subject}_{m.group(1)}"
                if tid in seen:
                    continue
                seen.add(tid)
                material = subj_dir / f"{subject}_material"
                tasks.append({
                    "subject": subject,
                    "number": m.group(1),
                    "md_path": md,
                    "material_path": material if material.is_dir() else None,
                })
    return tasks


def load_task_ids(path):
    lines = [ln.split("#", 1)[0].strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    return {ln for ln in lines if ln}


# --------------------------------------------------------------------------- #
# [Judge] stripping
# --------------------------------------------------------------------------- #
JUDGE_HEADER_RE = re.compile(r"^\s*\[Judge\]\s*$", re.MULTILINE)
SEP_RE = re.compile(r"^\s*---\s*$")


def strip_judge(md_text):
    """Remove the [Judge] section (and the '---' above it) so the executor never
    sees the answer key / grading criteria."""
    lines = md_text.splitlines()
    judge_idx = None
    for i, ln in enumerate(lines):
        if JUDGE_HEADER_RE.match(ln):
            judge_idx = i
            break
    if judge_idx is None:
        return md_text.rstrip() + "\n"
    sep_idx = None
    for i in range(judge_idx - 1, -1, -1):
        if SEP_RE.match(lines[i]):
            sep_idx = i
            break
    cut = sep_idx if sep_idx is not None else judge_idx
    kept = "\n".join(lines[:cut]).rstrip()
    return kept + "\n"


# --------------------------------------------------------------------------- #
# Staging
# --------------------------------------------------------------------------- #
def task_id(t):
    return f"{t['subject']}_{t['number']}"


def stage_task(t):
    tid = task_id(t)
    stage_dir = STAGE_ROOT / t["subject"] / tid
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    md_text = t["md_path"].read_text(encoding="utf-8", errors="replace")
    (stage_dir / "task.md").write_text(strip_judge(md_text), encoding="utf-8")

    if t["material_path"]:
        shutil.copytree(t["material_path"], stage_dir / t["material_path"].name)
    return stage_dir


# --------------------------------------------------------------------------- #
# Agent spawning
# --------------------------------------------------------------------------- #
def build_prompt(staged_task_path, stage_dir):
    return (
        f"Your task is to complete the task written in {staged_task_path}.\n\n"
        "Open and read that file in full. It is a verifiable research task: its "
        "[Agents] section tells you exactly what to do — read the given material "
        "(the *_material folder in this same directory), run the described "
        "experiment / analysis, and write your conclusion to the summary file "
        "named in the task. All relative paths (including ./summary*.md) are "
        "relative to THIS directory.\n\n"
        "IMPORTANT: there is intentionally NO answer key, NO [Judge] criteria, "
        "and NO provided standard answer anywhere — derive everything yourself "
        "from the material and your own measurements/code.\n\n"
        "Constraints: CPU-only (no GPU); keep the whole task well under 30 "
        "minutes; install any pip / apt dependencies you need. Do ALL of your "
        "work inside this directory and write all outputs here.\n\n"
        "When you are completely finished and the summary file has been written, "
        f"create an empty file named {DONE_SENTINEL} in this directory to signal "
        "completion, then stop."
    )


def spawn_agent(t, stage_dir):
    ensure_session()
    tid = task_id(t)
    seq = next_seq()
    win_name = sanitize_window_name(f"{tid}_{seq}")
    target = f"{TMUX_SESSION}:{win_name}"

    prefix = ("unset VSCODE_IPC_HOOK_CLI VSCODE_GIT_IPC_HANDLE "
              "VSCODE_GIT_ASKPASS_NODE VSCODE_GIT_ASKPASS_MAIN && "
              "export IS_SANDBOX=1 && ")
    parts = ["exec", "claude",
             "--settings", shlex.quote(str(CLAUDE_SETTINGS)),
             "--dangerously-skip-permissions",
             "--disallowedTools", "AskUserQuestion,ExitPlanMode"]
    if MODEL:
        parts += ["--model", str(MODEL)]
    claude_cmd = prefix + " ".join(parts)
    shell_cmd = f"bash -lc {shlex.quote(claude_cmd)}"

    tmux("new-window", "-d", "-t", TMUX_SESSION, "-n", win_name,
         "-c", str(stage_dir), shell_cmd, check=True)

    time.sleep(AGENT_BOOT_SECONDS)

    prompt = build_prompt(stage_dir / "task.md", stage_dir)
    prompt_file = stage_dir / ".prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    buf = f"prompt_{seq}"
    tmux("load-buffer", "-b", buf, str(prompt_file), check=True)
    tmux("paste-buffer", "-p", "-d", "-b", buf, "-t", target, check=True)
    for _ in range(3):
        tmux("send-keys", "-t", target, "Enter")
    return target


# --------------------------------------------------------------------------- #
# Completion waiting + finalization
# --------------------------------------------------------------------------- #
ONBOARD_MARKERS = ("Do you trust", "trust the files", "theme", "Reminder")


def wait_for_completion(target, stage_dir, timeout):
    deadline = time.time() + timeout
    last_len = -1
    stale_ticks = 0
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        if (stage_dir / DONE_SENTINEL).exists():
            return "done", capture_pane(target)
        if not pane_alive(target):
            return "dead", capture_pane(target)
        pane = capture_pane(target)
        (stage_dir / "_pane.log").write_text(pane, encoding="utf-8")
        if any(mk in pane for mk in ONBOARD_MARKERS):
            tmux("send-keys", "-t", target, "y")
            tmux("send-keys", "-t", target, "Enter")
        cur_len = len(pane)
        if cur_len == last_len:
            stale_ticks += 1
        else:
            stale_ticks = 0
            last_len = cur_len
        if stale_ticks == 0:
            log(f"      ...working (pane {cur_len}b)")
    return "timeout", capture_pane(target)


CODE_EXT = {".py", ".ipynb", ".sh", ".c", ".cc", ".cpp", ".h", ".hpp", ".rs",
            ".go", ".js", ".ts", ".m", ".jl", ".java"}
FIG_EXT  = {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".eps", ".gif"}
RES_EXT  = {".json", ".csv", ".tsv", ".npy", ".npz", ".log", ".txt", ".dat",
            ".out", ".yaml", ".yml", ".parquet", ".db"}
_DIR_MAP = {
    "code": "code", "src": "code",
    "figures": "figures", "figs": "figures", "plots": "figures",
    "results": "results", "output": "results", "outputs": "results",
    "data": "results", "raw": "results",
}
_STAGE_META = {".prompt.txt", "_pane.log", "_final_pane.log", DONE_SENTINEL, "task.md"}


def harvest_into(stage_dir, result_dir, full_task_path):
    """Copy the full original task spec + all agent artifacts from stage_dir into
    result_dir, classifying code/figures/results."""
    result_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(full_task_path, result_dir / "task.md")
    copied = []
    for p in sorted(stage_dir.iterdir()):
        n = p.name
        if n in _STAGE_META:
            continue
        if p.is_dir():
            if n.lower().endswith("_material") or n == "__pycache__":
                continue
            dest = _DIR_MAP.get(n.lower())
            if dest:
                shutil.copytree(p, result_dir / dest, dirs_exist_ok=True)
                copied.append(f"{dest}/")
            else:
                shutil.copytree(p, result_dir / "results" / n, dirs_exist_ok=True)
                copied.append(f"results/{n}/")
            continue
        if n.lower().startswith("summary"):
            shutil.copy2(p, result_dir / n)
            copied.append(n)
            continue
        ext = p.suffix.lower()
        if ext in (".pyc", ".pyo"):
            continue
        if ext in CODE_EXT:
            dest = result_dir / "code"
        elif ext in FIG_EXT:
            dest = result_dir / "figures"
        elif ext in RES_EXT:
            dest = result_dir / "results"
        else:
            shutil.copy2(p, result_dir / n)
            copied.append(n)
            continue
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest / n)
        copied.append(f"{dest.name}/{n}")
    return result_dir, sorted(set(copied))


def finalize(t, stage_dir):
    tid = task_id(t)
    result_dir = EXPERIMENTS_DIR / t["subject"] / f"{tid}_result"
    return harvest_into(stage_dir, result_dir, t["md_path"])


def process_task(t):
    tid = task_id(t)
    if tid in SKIPLIST:
        log(f"⊘ SKIP (skiplist) {tid}")
        return {"task": tid, "status": "skipped"}
    timeout = PRE_TIMEOUT if t["subject"] in PRE_EXISTING else args.timeout
    tag = "[pre-existing]" if t["subject"] in PRE_EXISTING else ""
    log(f"▶ START {tid} {tag} (timeout={timeout}s)")
    try:
        stage_dir = stage_task(t)
        target = spawn_agent(t, stage_dir)
        status, pane = wait_for_completion(target, stage_dir, timeout)
        (stage_dir / "_final_pane.log").write_text(pane, encoding="utf-8")
        tmux("kill-window", "-t", target)
        result = {"task": tid, "status": status, "stage": str(stage_dir)}
        if status == "done":
            result_dir, copied = finalize(t, stage_dir)
            result["result_dir"] = str(result_dir)
            result["copied"] = copied
            log(f"✓ DONE  {tid}  -> {result_dir.name}  ({', '.join(copied) or 'no summary?'})")
        else:
            log(f"✗ {status.upper()} {tid}  (pane tail in {stage_dir}/_final_pane.log)")
            if t["subject"] in PRE_EXISTING:
                reason = {"timeout": "exceeded short pre-existing budget",
                          "dead": "agent died",
                          "error": "error"}.get(status, status)
                with open(SKIPPED_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{tid}: {status.upper()} — {reason} (pre-existing, too heavy for <30min/CPU)\n")
                log(f"⊘ logged SKIPPED {tid}")
        return result
    except subprocess.CalledProcessError as e:
        log(f"✗ ERROR {tid}: {e} stderr={(e.stderr or '').strip()[:200]}")
        return {"task": tid, "status": "error", "error": str(e)}
    except Exception as e:  # noqa
        log(f"✗ ERROR {tid}: {type(e).__name__}: {e}")
        return {"task": tid, "status": "error", "error": str(e)}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def is_already_done(t):
    tid = task_id(t)
    rd = EXPERIMENTS_DIR / t["subject"] / f"{tid}_result"
    return rd.is_dir() and any(rd.glob("summary*"))


def main():
    ap = argparse.ArgumentParser(description="Phase-2 execution orchestrator (model-agnostic)")
    ap.add_argument("--model-config", required=True,
                    help="claude --settings JSON, e.g. /root/.claude/settings-qwen3.7-max.json")
    ap.add_argument("--experiment-cwd", required=True,
                    help="base temp/staging dir; each task runs in "
                         "<experiment-cwd>/<subject>/<subject>_<NN>/ (agent cwd)")
    ap.add_argument("--output-dir", required=True,
                    help="results output dir; _run_report.json is also written here")
    ap.add_argument("--tasks-file", required=True,
                    help="file of task IDs to run (one per line; '#' comments ok)")
    ap.add_argument("--model", default=None,
                    help="model name passed to claude --model (default: omit, "
                         "let --model-config decide)")
    ap.add_argument("--list", action="store_true", help="list discovered tasks and exit")
    ap.add_argument("--run", action="store_true", help="actually spawn agents (default: dry plan)")
    ap.add_argument("--subjects", nargs="*", help="further restrict to these subjects")
    ap.add_argument("--limit", type=int, help="process at most N tasks")
    ap.add_argument("--concurrency", type=int, default=1, help="parallel workers (default 1 = serial)")
    ap.add_argument("--timeout", type=int, default=TASK_TIMEOUT, help="per-task timeout (s)")
    ap.add_argument("--skip-done", action="store_true", help="skip tasks already finalized")
    ap.add_argument("--backfill", action="store_true",
                    help="re-harvest code/figures/results from stage dirs into "
                         "already-finalized result dirs (no agents spawned)")
    global args, MODEL, CLAUDE_SETTINGS, STAGE_ROOT, EXPERIMENTS_DIR
    global TMUX_SESSION, SKIPPED_FILE, SKIPLIST_FILE, SKIPLIST
    args = ap.parse_args()

    cfg = Path(args.model_config)
    if not cfg.is_file():
        sys.exit(f"ERROR: --model-config not found: {cfg}")
    CLAUDE_SETTINGS = str(cfg.resolve())
    MODEL = args.model
    STAGE_ROOT = Path(args.experiment_cwd).resolve()
    EXPERIMENTS_DIR = Path(args.output_dir).resolve()
    TMUX_SESSION = derive_session_name(EXPERIMENTS_DIR, cfg)
    SKIPPED_FILE = STAGE_ROOT / "_skipped.txt"
    SKIPLIST_FILE = STAGE_ROOT / "_skiplist.txt"

    tf = Path(args.tasks_file)
    if not tf.is_file():
        sys.exit(f"ERROR: --tasks-file not found: {tf}")
    allowed = load_task_ids(tf)

    if SKIPLIST_FILE.exists():
        SKIPLIST = {ln.strip() for ln in SKIPLIST_FILE.read_text().splitlines()
                    if ln.strip() and not ln.startswith("#")}
        log(f"skiplist loaded: {sorted(SKIPLIST)}")

    log(f"model-config : {CLAUDE_SETTINGS}" + (f"  (--model {MODEL})" if MODEL else "  (--model from config)"))
    log(f"experiment   : temp/stage (agent cwd) -> {STAGE_ROOT}")
    log(f"results      : output dir             -> {EXPERIMENTS_DIR}")
    log(f"tmux session : {TMUX_SESSION}")

    tasks = discover_tasks()
    if args.subjects:
        want = set(args.subjects)
        tasks = [t for t in tasks if t["subject"] in want]
    before = len(tasks)
    tasks = [t for t in tasks if task_id(t) in allowed]
    missing = sorted(allowed - {task_id(t) for t in tasks})
    log(f"--tasks-file {args.tasks_file}: {len(tasks)}/{before} discovered task(s) match"
        + (f"; {len(missing)} id(s) not found: {missing}" if missing else ""))
    if args.limit:
        tasks = tasks[:args.limit]

    if args.backfill:
        n_ok = 0
        for t in tasks:
            tid = task_id(t)
            stage_dir = STAGE_ROOT / t["subject"] / tid
            result_dir = EXPERIMENTS_DIR / t["subject"] / f"{tid}_result"
            if stage_dir.is_dir() and result_dir.is_dir():
                _, copied = harvest_into(stage_dir, result_dir, t["md_path"])
                n_ok += 1
                log(f"  backfilled {tid}: {', '.join(copied) or 'no artifacts'}")
        log(f"==== BACKFILL done: {n_ok} task(s) re-harvested ====")
        return

    if args.list or not args.run:
        print("\n--- task plan (dry) ---")
        for t in tasks:
            done = "✓" if is_already_done(t) else " "
            print(f"  {done} {task_id(t):24}  material={'yes' if t['material_path'] else 'NO'}")
        print(f"\n{len(tasks)} task(s). Run with --run to execute.")
        return

    if args.skip_done:
        before = len(tasks)
        tasks = [t for t in tasks if not is_already_done(t)]
        log(f"--skip-done: {before - len(tasks)} already finalized, {len(tasks)} to go")

    # NEW subjects first; PRE-EXISTING last (short budget, skip-on-timeout).
    tasks.sort(key=lambda t: (0 if t["subject"] not in PRE_EXISTING else 1,
                              t["subject"], int(t["number"])))
    log(f"order: NEW subjects first, then pre-existing {sorted(PRE_EXISTING)} (short {PRE_TIMEOUT}s budget)")

    STAGE_ROOT.mkdir(parents=True, exist_ok=True)
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = EXPERIMENTS_DIR / "_run_report.json"
    results = []

    if args.concurrency <= 1:
        for t in tasks:
            results.append(process_task(t))
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(process_task, t): t for t in tasks}
            for f in as_completed(futs):
                results.append(f.result())

    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False),
                           encoding="utf-8")
    ok = sum(1 for r in results if r.get("status") == "done")
    bad = len(results) - ok
    log(f"==== FINISHED: {ok} done / {bad} not-done; report -> {report_path} ====")


if __name__ == "__main__":
    main()
