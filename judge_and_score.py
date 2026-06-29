#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_and_score.py
==================
Scan an experiment result directory and JUDGE each task against its
`[Judge V2]` standard, using the JUDGE_MODEL API **directly** (no claude code /
codex). Renamed/generalized successor of judge_minimax_glm.py — what used to be
hardcoded (result dir, task set) is now two REQUIRED CLI arguments.

Required arguments:
  --result-dir   directory produced by solve_tasks.py (per-task results +
                 _run_report.json); the judge also writes its own report /
                 detail / cache / per-task LLM logs HERE.
  --tasks-file   file of task IDs to judge (one per line; '#' comments ok).

Per task the verdict falls into one of SIX buckets:

    Normal (V2 has a real, measured golden — judgeable):
        success / failed / timeout
    Special "Unknown-Judge" (V2 itself declares the experiment CANNOT be
    completed — 无实测 / 无法执行 / 言之有理即给分 — no real golden, counted in
    NONE of the three normal buckets):
        未知Judge-成功 / 未知Judge-失败 / 未知Judge-超时

Outputs (all under <result-dir>/):
    _judge_detail.json    per-task verdict + reasoning + v2_infeasible flag
    _judge_report.md      human-readable 6-bucket summary
    _judge_cache.json     resumable cache of judge calls
    judge_llm/<task>.log  complete raw request/response per task

Usage:
    python3 judge_and_score.py --result-dir <DIR> --tasks-file tasks_filtered.txt
    python3 judge_and_score.py ... --concurrency 4
    python3 judge_and_score.py ... --only tsne_02 zdt_01   # bypass tasks-file
    python3 judge_and_score.py ... --redo                  # ignore cache
    python3 judge_and_score.py ... --report-only           # rebuild from cache
"""

import argparse
import json
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# --------------------------------------------------------------------------- #
# Location (derived from this file so the script runs from any cwd)
# --------------------------------------------------------------------------- #
WORKSPACE = Path(__file__).resolve().parent.parent          # .../happy_lake
REPO      = Path(__file__).resolve().parent                  # .../team_bench_gen
CANDIDATE_SPEC_DIRS = [
    REPO / "generated_task_await_verify",
    REPO / "generated_task_verified",
    REPO / "generated_task_long_experiment",
]

# --------------------------------------------------------------------------- #
# Judge LLM endpoint (edit here to change the judge model, then --redo)
# --------------------------------------------------------------------------- #
JUDGE_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
JUDGE_API_KEY  = "b13cebf2b0f74f3a8d3ba0875961abb8.YI3KulWcI0rT6JNd"
JUDGE_MODEL    = "GLM-5.1"

# Assigned in main() from the required CLI args:
RESULTS_ROOT = None          # <result-dir>
RUN_REPORT   = None          # <result-dir>/_run_report.json
DETAIL_PATH  = None          # <result-dir>/_judge_detail.json
REPORT_PATH  = None          # <result-dir>/_judge_report.md
CACHE_PATH   = None          # <result-dir>/_judge_cache.json
LLM_LOG_DIR  = None          # <result-dir>/judge_llm

# evidence size caps (chars)
CAP_SUMMARY = 14000
CAP_RESULTS = 14000
CAP_CODE    = 8000
MAX_CODE_FILES = 6
GLM_MAX_TOKENS  = 4096          # thinking disabled -> answer only
GLM_CALL_TIMEOUT = 220
MAX_RETRIES     = 4
PARSE_RETRIES   = 3
DEFAULT_CONCURRENCY = 4         # >4 tends to congest the GLM endpoint under load

# Keywords meaning V2 itself declares the experiment CANNOT be completed.
INFEASIBLE_MARKERS = (
    "言之有理", "无实测", "无法执行", "超时未交卷",
    "未产出 summary", "未产出summary",
    "不可能完成", "无法完成", "难以完成",
)

BUCKET_LABEL = {
    "success":          "✅ 成功 (success)",
    "failed":           "❌ 失败 (failed)",
    "timeout":          "⏱  超时 (timeout)",
    "unknown_success":  "❔ 未知Judge-成功",
    "unknown_failed":   "❔ 未知Judge-失败",
    "unknown_timeout":  "❔ 未知Judge-超时",
}


def log(msg):
    print(msg, flush=True)


def read_text(path, cap):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read(cap)
    except Exception:
        return ""


def task_dir(subj, num):
    return RESULTS_ROOT / subj / f"{subj}_{num}_result"


# --------------------------------------------------------------------------- #
# V2 extraction + infeasibility detection
# --------------------------------------------------------------------------- #
def extract_judge_v2(text):
    i = text.find("[Judge V2]")
    if i < 0:
        return ""
    rest = text[i:]
    j = rest.find("<!-- judge-v2 authored-by")
    if j > 0:
        rest = rest[:j]
    return rest.strip()


def canonical_spec_path(subj, num):
    """Find the canonical spec carrying [Judge V2]: candidate source dirs first,
    then the full spec archived in the result dir."""
    tid = f"{subj}_{num}"
    for d in CANDIDATE_SPEC_DIRS:
        p = d / subj / f"{tid}.md"
        if p.is_file():
            return p
    return RESULTS_ROOT / subj / f"{tid}_result" / "task.md"


def load_v2_text(task_id):
    subj, num = task_id.rsplit("_", 1)
    src = canonical_spec_path(subj, num)
    if not src.is_file():
        return ""
    return extract_judge_v2(read_text(src, 60000))


def is_v2_infeasible(v2_text):
    return any(m in v2_text for m in INFEASIBLE_MARKERS)


# --------------------------------------------------------------------------- #
# Judge LLM direct call (thinking disabled -> reliable structured output)
# --------------------------------------------------------------------------- #
_LLM_LOG_LOCK = threading.Lock()
_LLM_LOG_SEEN = set()


def log_llm_io(log_id, messages, content, note=""):
    """Write the COMPLETE, RAW judge request + response for one call to a
    PER-TASK file <task_id>.log — only the string payloads, all metadata
    stripped. First write for a task truncates; later attempts append.
    Thread-safe; never raises into the caller."""
    try:
        task_id = log_id.split("#", 1)[0]
        sys_msg = next((m.get("content", "") for m in messages if m.get("role") == "system"), "")
        usr_msg = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        bar = "=" * 90
        block = (
            f"[{log_id}]  {ts}  {note}\n".rstrip() + "\n" +
            f"{bar}\n"
            f"---- REQUEST · system ----\n{sys_msg}\n"
            f"---- REQUEST · user ----\n{usr_msg}\n"
            f"---- RESPONSE · content ----\n{content if content is not None else ''}\n"
            f"{bar}\n"
        )
        with _LLM_LOG_LOCK:
            first = task_id not in _LLM_LOG_SEEN
            _LLM_LOG_SEEN.add(task_id)
            path = LLM_LOG_DIR / f"{task_id}.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w" if first else "a", encoding="utf-8") as fh:
                fh.write(block if first else "\n" + block)
    except Exception as e:  # logging must never break judging
        log(f"    [llm-log] write failed for {log_id}: {e}")


def glm_chat(messages, timeout=GLM_CALL_TIMEOUT, log_id=None):
    payload = {
        "model": JUDGE_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": GLM_MAX_TOKENS,
        "thinking": {"type": "disabled"},
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {JUDGE_API_KEY}",
        "Content-Type": "application/json",
    }
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(JUDGE_BASE_URL, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            content = (body["choices"][0].get("message") or {}).get("content") or ""
            if not content.strip():
                raise RuntimeError("empty content")
            if log_id:
                log_llm_io(log_id, messages, content, note=f"transport-attempt {attempt}")
            return content
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {e.reason}"
            if e.code == 429 or 500 <= e.code < 600:
                wait = min(2 ** attempt, 20)
                log(f"    [glm] {last_err} — retry {attempt}/{MAX_RETRIES} in {wait}s")
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, RuntimeError) as e:
            last_err = f"{type(e).__name__}: {e}"
            wait = min(2 ** attempt, 20)
            log(f"    [glm] {last_err} — retry {attempt}/{MAX_RETRIES} in {wait}s")
            time.sleep(wait)
            continue
    if log_id:
        log_llm_io(log_id, messages, "", note=f"FAILED after {MAX_RETRIES} retries: {last_err}")
    raise RuntimeError(f"GLM call failed after {MAX_RETRIES} retries: {last_err}")


# --------------------------------------------------------------------------- #
# evidence gathering
# --------------------------------------------------------------------------- #
def gather_summary(result_dir):
    cands = sorted(result_dir.glob("summary_*.md"))
    return read_text(cands[0], CAP_SUMMARY) if cands else ""


def gather_results(result_dir):
    rdir = result_dir / "results"
    if not rdir.is_dir():
        return ""
    chunks, used = [], 0
    files = sorted(
        list(rdir.glob("*.json")) + list(rdir.glob("*.csv")) + list(rdir.glob("*.txt")),
        key=lambda p: p.stat().st_size,
    )
    for p in files:
        if used >= CAP_RESULTS:
            break
        raw = read_text(p, CAP_RESULTS - used)
        if not raw:
            continue
        chunks.append(f"### {p.name} (first {len(raw)} chars)\n```\n{raw}\n```")
        used += len(raw) + 40
    return "\n\n".join(chunks)


def gather_code(result_dir):
    cdir = result_dir / "code"
    if not cdir.is_dir():
        return ""
    exts = (".py", ".cpp", ".c", ".cc", ".java", ".go", ".rs", ".m",
            ".sh", ".jl", ".rb", ".js", ".ts")
    files = [p for p in sorted(cdir.rglob("*")) if p.suffix.lower() in exts]
    if not files:
        files = sorted(cdir.rglob("*"))[:MAX_CODE_FILES]
    chunks, used = [], 0
    for p in files[:MAX_CODE_FILES]:
        if used >= CAP_CODE:
            break
        rel = p.relative_to(cdir)
        raw = read_text(p, min(2500, CAP_CODE - used))
        chunks.append(f"### {rel}\n```\n{raw}\n```")
        used += len(raw) + 40
    return "\n\n".join(chunks)


def gather_figures_list(result_dir):
    fdir = result_dir / "figures"
    if not fdir.is_dir():
        return ""
    imgs = [p.name for p in fdir.iterdir()
            if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".pdf")]
    return ", ".join(imgs) if imgs else ""


# --------------------------------------------------------------------------- #
# judge prompt + verdict parsing
# --------------------------------------------------------------------------- #
SYSTEM_PROMPT = """你是一名严格但公正的实验评审。判断一份提交的实验是否满足给定的 [Judge V2] 评分标准。

评审原则：
1. 以 [Judge V2] 为唯一评分依据（含 golden基准实验数值 与 可接受范围）。
2. 优先核对 REAL 实测数据（results/*.json|csv），而非仅相信 summary 自述；数字与 results 一致才采信，矛盾或缺失则存疑。
3. 每条定量标准：核对实测值是否落在"可接受 ∈[a,b]"范围内、是否与 golden 方向一致。
4. PASS：核心（含 golden 的）标准基本满足、数值在范围内。FAIL：核心标准未满足、关键数值错误/超范围、结果明显编造、或与 V2 要求无关。
5. 不因排版/语言/非核心细节扣分，只看科学正确性是否达到 V2。

只输出一个 JSON 对象（不要 markdown 代码块、不要任何额外文字）：
{"verdict":"PASS 或 FAIL","score":0到100整数,"met":["满足点"],"unmet":["未满足点"],"reasoning":"<=200字中文"}"""


def build_user_prompt(judge_v2, summary, results, code, figures, task_id):
    parts = [f"任务ID: {task_id}", "", "===== [Judge V2] 评分标准 =====", judge_v2 or "(未找到 [Judge V2] 块)"]
    parts += ["", "===== 提交证据：实验摘要 (summary_*.md) =====", summary or "(无 summary)"]
    if results:
        parts += ["", "===== 提交证据：实测数据 (results/) =====", results]
    if code:
        parts += ["", "===== 提交证据：源码片段 (code/, 截断) =====", code]
    if figures:
        parts += ["", f"(另有图片: {figures})"]
    parts += ["", "请依据 [Judge V2] 判定，只输出 JSON。"]
    return "\n".join(parts)


JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_verdict(content):
    """Parse judge output into a verdict dict. Tolerant of malformed/truncated
    JSON: tries strict json.loads on the {...} block, then regex-extracts
    verdict/score/reasoning field-by-field."""
    raw = (content or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    obj = None
    m = JSON_RE.search(raw)
    if m:
        try:
            obj = json.loads(m.group(0))
        except Exception:
            obj = None
    if not isinstance(obj, dict):
        obj = {}
        vm = re.search(r'"verdict"\s*:\s*"?\s*(PASS|FAIL)\b', raw, re.I)
        sm = re.search(r'"score"\s*:\s*"?\s*(\d{1,3})', raw)
        rm = re.search(r'"reasoning"\s*:\s*"((?:[^"\\]|\\.)*)"', raw)
        obj["verdict"]  = vm.group(1).upper() if vm else ""
        obj["score"]    = int(sm.group(1)) if sm else None
        obj["met"]      = []
        obj["unmet"]    = []
        obj["reasoning"] = rm.group(1) if rm else raw[:200]

    v = str(obj.get("verdict", "")).strip().upper()
    if v not in ("PASS", "FAIL"):
        try:
            v = "PASS" if int(obj.get("score", 0)) >= 60 else "FAIL"
        except Exception:
            v = "FAIL"
    obj["verdict"] = v
    obj.setdefault("score", None)
    obj.setdefault("met", [])
    obj.setdefault("unmet", [])
    obj.setdefault("reasoning", "")
    return obj, raw


# --------------------------------------------------------------------------- #
# per-task judging
# --------------------------------------------------------------------------- #
def judge_task(task_id, force, cache, infeasible):
    subj, num = task_id.rsplit("_", 1)
    rdir = task_dir(subj, num)
    base = {"task": task_id, "v2_infeasible": bool(infeasible.get(task_id, False))}
    if not rdir.is_dir():
        return {**base, "judged": False, "error": "result dir missing"}

    if cache is not None and not force and task_id in cache and cache[task_id].get("judged"):
        return cache[task_id]

    judge_v2 = load_v2_text(task_id)
    summary  = gather_summary(rdir)
    results  = gather_results(rdir)
    code     = gather_code(rdir)
    figures  = gather_figures_list(rdir)

    if not judge_v2:
        return {**base, "judged": True, "verdict": "FAIL", "score": 0,
                "reasoning": "未找到 [Judge V2] 评分标准",
                "met": [], "unmet": ["missing Judge V2"], "raw": ""}

    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(judge_v2, summary, results, code, figures, task_id)},
    ]
    last_err = None
    verdict = None
    raw = ""
    for attempt in range(1, PARSE_RETRIES + 1):
        try:
            content = glm_chat(msgs, log_id=f"{task_id}#{attempt}")
        except Exception as e:
            return {**base, "judged": False, "error": f"glm call failed: {e}"}
        verdict, raw = parse_verdict(content)
        if verdict is not None:
            break
        last_err = f"unparseable verdict (attempt {attempt}): {raw[:160]}"
        log(f"    [parse] {task_id}: {last_err} — re-calling")
    if verdict is None:
        return {**base, "judged": False, "error": last_err or "unparseable verdict"}
    return {**base, "judged": True, "verdict": verdict["verdict"], "score": verdict["score"],
            "met": verdict["met"], "unmet": verdict["unmet"],
            "reasoning": verdict["reasoning"], "raw": raw[:1500]}


# --------------------------------------------------------------------------- #
# aggregation into six buckets
# --------------------------------------------------------------------------- #
def aggregate(detail, statuses, infeasible):
    b = {k: [] for k in BUCKET_LABEL}
    b["unjudged"] = []
    for task_id, st in statuses.items():
        infeas = infeasible.get(task_id, False)
        if st == "timeout":
            base = "timeout"
        elif st == "error":
            base = "failed"
        elif st == "done":
            d = detail.get(task_id)
            if not d or not d.get("judged"):
                b["unjudged"].append(task_id); continue
            base = "success" if d.get("verdict") == "PASS" else "failed"
        else:
            b["unjudged"].append(task_id); continue
        b[("unknown_" if infeas else "") + base].append(task_id)
    return b


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def write_report(buckets, detail, statuses, infeasible):
    L = []
    L.append(f"# Experiment Results — {JUDGE_MODEL} Judge Report")
    L.append("")
    L.append(f"Verdict: orchestrator status + {JUDGE_MODEL} judging each `done` task vs `[Judge V2]`. "
             "Tasks whose V2 declares the experiment **cannot be completed** (无实测/无法执行/言之有理即给分) "
             "are separated into **未知Judge** buckets — counted in NONE of 成功/失败/超时.")
    L.append("")
    L.append(f"## Six-bucket headline (of {len(statuses)} tasks)")
    L.append("")
    L.append("| bucket | count |")
    L.append("| --- | --- |")
    order = ["success", "failed", "timeout", "unknown_success", "unknown_failed", "unknown_timeout"]
    for k in order:
        L.append(f"| {BUCKET_LABEL[k]} | **{len(buckets[k])}** |")
    if buckets["unjudged"]:
        L.append(f"| ❔ unjudged | {len(buckets['unjudged'])} |")
    total = sum(len(buckets[k]) for k in order) + len(buckets["unjudged"])
    L.append(f"| **total** | {total} |")
    L.append("")

    feas_n = sum(len(buckets[k]) for k in ("success", "failed", "timeout"))
    infeas_n = sum(len(buckets[k]) for k in ("unknown_success", "unknown_failed", "unknown_timeout"))
    L.append(f"- V2 with real golden (judgeable): **{feas_n}** "
             f"→ 成功 {len(buckets['success'])} / 失败 {len(buckets['failed'])} / 超时 {len(buckets['timeout'])}")
    L.append(f"- V2 declares experiment infeasible: **{infeas_n}** "
             f"→ 未知Judge-成功 {len(buckets['unknown_success'])} / 未知Judge-失败 {len(buckets['unknown_failed'])} / 未知Judge-超时 {len(buckets['unknown_timeout'])}")
    L.append("")

    L.append("## Per-subject breakdown")
    L.append("")
    L.append("| subject | success | failed | timeout | 未知-成功 | 未知-失败 | 未知-超时 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- |")
    subjects = sorted({t.rsplit("_", 1)[0] for t in statuses})
    for subj in subjects:
        row = [subj]
        for k in order:
            row.append(str(sum(1 for t in buckets[k] if t.startswith(subj + "_"))))
        L.append("| " + " | ".join(row) + " |")
    L.append("")

    for key, title in (("failed", "## 失败 (failed) — V2 feasible"),
                       ("unknown_failed", "## 未知Judge-失败 — V2 infeasible + judged FAIL/error")):
        L.append(title)
        L.append("")
        if buckets[key]:
            for t in sorted(buckets[key]):
                d = detail.get(t)
                if d and d.get("judged"):
                    reason = (d.get("reasoning") or "").replace("\n", " ").strip()[:220]
                    L.append(f"- **{t}** (FAIL, score={d.get('score')}) — {reason}")
                elif statuses.get(t) == "error":
                    L.append(f"- **{t}** — orchestrator error (could not run)")
                else:
                    L.append(f"- **{t}** — (not judged)")
        else:
            L.append("_(none)_")
        L.append("")

    for key, title in (("timeout", "## 超时 (timeout) — V2 feasible"),
                       ("unknown_timeout", "## 未知Judge-超时 — V2 infeasible + orchestrator timeout")):
        L.append(title)
        L.append("")
        L.append(", ".join(sorted(buckets[key])) if buckets[key] else "_(none)_")
        L.append("")

    L.append("## 未知Judge 任务清单 (V2 declares experiment cannot be completed)")
    L.append("")
    inflist = sorted(t for t in statuses if infeasible.get(t))
    if inflist:
        L.append(", ".join(inflist))
    else:
        L.append("_(none)_")
    L.append("")

    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")
    return "\n".join(L)


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_task_list(path):
    try:
        lines = [ln.split("#", 1)[0].strip() for ln in path.read_text(encoding="utf-8").splitlines()]
        return {ln for ln in lines if ln}
    except Exception:
        return set()


def save_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Judge + score experiment results with the judge LLM directly.")
    ap.add_argument("--result-dir", required=True,
                    help="experiment result dir from solve_tasks.py (per-task results "
                         "+ _run_report.json); judge outputs also go here")
    ap.add_argument("--tasks-file", required=True,
                    help="file of task IDs to judge (one per line; '#' comments ok)")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--limit",  type=int, default=0, help="judge only first N done tasks (smoke test)")
    ap.add_argument("--only",  nargs="+", default=[], help="judge only these task ids (bypasses --tasks-file)")
    ap.add_argument("--redo",  action="store_true", help="ignore cache, re-judge")
    ap.add_argument("--report-only", action="store_true", help="skip judging, rebuild report from cache")
    args = ap.parse_args()

    global RESULTS_ROOT, RUN_REPORT, DETAIL_PATH, REPORT_PATH, CACHE_PATH, LLM_LOG_DIR
    RESULTS_ROOT = Path(args.result_dir).resolve()
    if not RESULTS_ROOT.is_dir():
        sys.exit(f"ERROR: --result-dir not found: {RESULTS_ROOT}")
    RUN_REPORT  = RESULTS_ROOT / "_run_report.json"
    DETAIL_PATH = RESULTS_ROOT / "_judge_detail.json"
    REPORT_PATH = RESULTS_ROOT / "_judge_report.md"
    CACHE_PATH  = RESULTS_ROOT / "_judge_cache.json"
    LLM_LOG_DIR = RESULTS_ROOT / "judge_llm"

    allowed = load_task_list(Path(args.tasks_file))
    log(f"result-dir  : {RESULTS_ROOT}")
    log(f"tasks-file  : {args.tasks_file}  ({len(allowed)} id(s))")
    log(f"judge model : {JUDGE_MODEL} @ {JUDGE_BASE_URL}  (thinking disabled)")

    # orchestrator statuses: from run report if present, else infer from result dirs
    run_report = load_json(RUN_REPORT, [])
    if run_report:
        log(f"run report  : {RUN_REPORT} ({len(run_report)} rows)")
    else:
        log(f"run report  : not found at {RUN_REPORT} — will infer status from result dirs")
    statuses = {row["task"]: row.get("status", "?") for row in run_report}
    for tid in allowed:
        if tid in statuses:
            continue
        subj, num = tid.rsplit("_", 1)
        rd = RESULTS_ROOT / subj / f"{tid}_result"
        statuses[tid] = "done" if (rd.is_dir() and any(rd.glob("summary*"))) else "absent"
    # restrict to the task list
    statuses = {t: s for t, s in statuses.items() if t in allowed}

    log("orchestrator status: " + ", ".join(
        f"{s}={sum(1 for v in statuses.values() if v == s)}"
        for s in ("done", "error", "timeout", "absent")))

    # precompute infeasibility for all tasks (from the canonical V2)
    infeasible = {}
    for t in statuses:
        try:
            infeasible[t] = is_v2_infeasible(load_v2_text(t))
        except Exception:
            infeasible[t] = False
    n_inf = sum(infeasible.values())
    log(f"V2 infeasible (cannot-complete) tasks: {n_inf}  /  feasible: {len(statuses) - n_inf}")

    cache  = {} if args.redo else load_json(CACHE_PATH, {})
    detail = load_json(DETAIL_PATH, {})
    for k, v in cache.items():
        if v.get("judged"):
            detail.setdefault(k, v)

    if args.only:
        to_judge_all = [t for t in args.only if t in statuses]
    else:
        to_judge_all = [t for t in statuses if statuses[t] == "done"]
    if args.limit:
        to_judge_all = to_judge_all[:args.limit]

    todo = ([] if args.report_only else
            [t for t in to_judge_all
             if not (not args.redo and t in cache and cache[t].get("judged"))])
    log(f"tasks to judge now: {len(todo)}  (cached judged: {sum(1 for v in cache.values() if v.get('judged'))})")

    if todo and not args.report_only:
        done_n = 0
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(judge_task, t, args.redo, cache, infeasible): t for t in todo}
            for fut in as_completed(futs):
                t = futs[fut]
                try:
                    res = fut.result()
                except Exception as e:
                    res = {"task": t, "judged": False,
                           "error": f"exception: {e}\n{traceback.format_exc()[:300]}"}
                cache[t] = res
                if res.get("judged"):
                    detail[t] = res
                done_n += 1
                tag = res.get("verdict", "?") if res.get("judged") else "ERR:" + str(res.get("error", ""))[:40]
                flag = " [infeasible-V2]" if infeasible.get(t) else ""
                log(f"  [{done_n}/{len(todo)}] {t:18} -> {tag}{flag}")
                if done_n % 5 == 0:
                    save_json(CACHE_PATH, cache)
                    save_json(DETAIL_PATH, detail)
        save_json(CACHE_PATH, cache)
        save_json(DETAIL_PATH, detail)

    buckets = aggregate(detail, statuses, infeasible)
    write_report(buckets, detail, statuses, infeasible)

    log("")
    log("=" * 64)
    log(f"JUDGE & SCORE SUMMARY — {JUDGE_MODEL}")
    log("=" * 64)
    for k in ("success", "failed", "timeout",
              "unknown_success", "unknown_failed", "unknown_timeout"):
        log(f"  {BUCKET_LABEL[k]:28} {len(buckets[k])}")
    if buckets["unjudged"]:
        log(f"  {'unjudged':28} {len(buckets['unjudged'])}  (re-run to judge them)")
    done = [t for t, s in statuses.items() if s == "done"]
    judged = [t for t in done if detail.get(t, {}).get("judged")]
    passed = [t for t in judged if detail.get(t, {}).get("verdict") == "PASS"]
    scores = [detail[t].get("score") for t in judged
              if isinstance(detail[t].get("score"), (int, float))]
    if judged:
        log("")
        log(f"  done tasks judged: {len(judged)}/{len(done)}  "
            f"(PASS {len(passed)} / FAIL {len(judged) - len(passed)})  "
            f"pass-rate {100.0 * len(passed) / len(judged):.1f}%")
    if scores:
        log(f"  mean score (judged): {sum(scores) / len(scores):.1f} / 100")
    log("")
    log(f"  report -> {REPORT_PATH}")
    log(f"  detail -> {DETAIL_PATH}")
    log(f"  cache  -> {CACHE_PATH}")


if __name__ == "__main__":
    main()
