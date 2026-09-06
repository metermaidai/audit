#!/usr/bin/env python3
"""
metermaid trajectory audit — trace-level waste in public agent trajectories.

Reads agent trajectories in the common public formats and runs the trace-level
detectors (loops, identical retries, context bloat, abandoned runs, step-count
outliers), pricing each finding from the trajectory's own cost when present.

Supported inputs (auto-detected per file):
  - SWE-agent        *.traj            {"trajectory":[{action,observation,response,...}], "info":{"model_stats":{...}}}
  - mini-swe-agent   *.traj.json       {"messages":[{role,content}], "info":{"model_stats":{...}}}
  - OpenHands        output.jsonl      one JSON per line with "history":[events], "metrics":{"accumulated_cost":...}
  - generic          *.json / *.jsonl  {"messages":[...]} or {"trajectory":[...]} or {"steps":[...]}

Usage:
  python trajectory_audit.py PATH [PATH ...] --out ./traj-audit
  python trajectory_audit.py experiments/evaluation/verified/2025*/trajs --label-by-parent
  python trajectory_audit.py --demo

A PATH can be a file or a directory (searched recursively). Each top-level PATH
(or each parent folder with --label-by-parent) becomes one "submission" in the report.

Fallback pricing when a trajectory carries no cost: --price-in / --price-out (USD per 1M tokens)
applied to tokens_sent/tokens_received if present, else to chars/4.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path

ERROR_MARKERS = ("Traceback", "Error:", "error:", "ERROR", "not found", "No such file",
                 "command not found", "SyntaxError", "failed", "FAILED", "Permission denied",
                 "Exception", "exit code 1", "returned non-zero")
SUBMIT_MARKERS = ("submit", "finish", "AgentFinishAction", "task_complete", "final_answer")
STATE_CHANGE = re.compile(r"(str_replace|\bedit\b|\bcreate\b|\bwrite\b|\binsert\b|\bappend\b|\brm\b|\bmv\b|\bcp\b|sed -i|"
                          r"\btouch\b|\bmkdir\b|\bpatch\b|pip install|npm install|git (apply|checkout|stash|reset|commit)|"
                          r"\becho\b[^|]*>|\bcat\b[^|]*>|new_str|file_text|\"command\": \"(create|str_replace|insert)\")", re.I)


@dataclass
class Step:
    action: str
    observation: str
    response_len: int = 0


@dataclass
class Traj:
    id: str
    submission: str
    fmt: str
    steps: list[Step]
    cost: float | None = None          # USD, from the trajectory itself if present
    tokens_in: int | None = None
    tokens_out: int | None = None
    api_calls: int | None = None
    exit_status: str | None = None
    cost_source: str = "none"          # reported | tokens | chars
    resolved: bool | None = None       # task outcome when the dataset carries it


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------
def _model_stats(info: dict) -> dict:
    ms = (info or {}).get("model_stats") or {}
    return {
        "cost": ms.get("instance_cost", ms.get("total_cost")),
        "tokens_in": ms.get("tokens_sent", ms.get("input_tokens")),
        "tokens_out": ms.get("tokens_received", ms.get("output_tokens")),
        "api_calls": ms.get("api_calls"),
    }


def parse_sweagent(d: dict, tid: str, sub: str) -> Traj | None:
    traj = d.get("trajectory")
    if not isinstance(traj, list) or not traj or not isinstance(traj[0], dict) or "action" not in traj[0]:
        return None
    steps = [Step(str(t.get("action") or ""), str(t.get("observation") or ""), len(str(t.get("response") or "")))
             for t in traj]
    info = d.get("info") or {}
    ms = _model_stats(info)
    return Traj(tid, sub, "sweagent", steps, ms["cost"], ms["tokens_in"], ms["tokens_out"], ms["api_calls"],
                info.get("exit_status"))


def parse_messages(msgs: list, tid: str, sub: str, info: dict | None, fmt: str) -> Traj | None:
    """Assistant message -> action; following user/tool message -> observation."""
    if not isinstance(msgs, list) or not msgs:
        return None
    steps: list[Step] = []
    pending = None
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").lower()
        role = {"ai": "assistant", "agent": "assistant", "model": "assistant", "human": "user",
                "tool_result": "tool", "function": "tool", "environment": "tool", "env": "tool"}.get(role, role)
        content = m.get("content")
        if content is None:
            content = m.get("text") if m.get("text") is not None else m.get("message")
        tool_uses = []
        tool_results = []
        if isinstance(content, list):  # Anthropic-style blocks
            texts = []
            for c in content:
                if not isinstance(c, dict):
                    texts.append(str(c)); continue
                ct = c.get("type")
                if ct == "tool_use":
                    tool_uses.append({"name": c.get("name"), "input": c.get("input")})
                elif ct == "tool_result":
                    rc = c.get("content")
                    if isinstance(rc, list):
                        rc = " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in rc)
                    tool_results.append(str(rc or ""))
                else:
                    texts.append(str(c.get("text") or c.get("content") or ""))
            content = " ".join(texts + tool_results)
        content = str(content or "")
        if tool_results and role == "user":
            role = "tool"
        if role == "assistant":
            if pending is not None:
                steps.append(Step(pending, "", 0))
            tcs = m.get("tool_calls")
            if tool_uses:
                pending = json.dumps(tool_uses, sort_keys=True, default=str)
            elif tcs:
                pending = json.dumps([tc.get("function", tc) for tc in tcs], sort_keys=True, default=str)
            else:
                pending = extract_action(content)
        elif role in ("user", "tool") and pending is not None:
            steps.append(Step(pending, content, 0))
            pending = None
    if pending is not None:
        steps.append(Step(pending, "", 0))
    if not steps:
        return None
    ms = _model_stats(info or {})
    return Traj(tid, sub, fmt, steps, ms["cost"], ms["tokens_in"], ms["tokens_out"], ms["api_calls"],
                (info or {}).get("exit_status"))


def extract_action(text: str) -> str:
    """Pull the command from a fenced block or last line; fall back to whole text."""
    m = re.findall(r"```(?:\w+)?\n(.*?)```", text, re.S)
    if m:
        return m[-1].strip()
    lines = [l for l in text.strip().splitlines() if l.strip()]
    return lines[-1].strip() if lines else text.strip()


def parse_openhands(d: dict, tid: str, sub: str) -> Traj | None:
    hist = d.get("history")
    if not isinstance(hist, list):
        return None
    steps: list[Step] = []
    pending = None
    exit_status = None
    for ev in hist:
        if not isinstance(ev, dict):
            continue
        if ev.get("action"):
            if ev.get("source") != "agent":
                continue
            args = ev.get("args") or {}
            act = ev["action"]
            if act in ("finish",) or "Finish" in str(ev.get("action")):
                exit_status = "submitted"
            key = args.get("command") or args.get("code") or args.get("path") or ev.get("message") or ""
            pending = f"{act}:{key}".strip()
            if isinstance(args, dict) and act in ("edit", "str_replace_editor"):
                pending = f"{act}:{args.get('path','')}:{args.get('command','')}:{str(args.get('old_str', args.get('new_str','')))[:200]}"
        elif ev.get("observation") is not None and pending is not None:
            steps.append(Step(pending, str(ev.get("content") or ""), 0))
            pending = None
    if pending is not None:
        steps.append(Step(pending, "", 0))
    if not steps:
        return None
    metrics = d.get("metrics") or {}
    cost = metrics.get("accumulated_cost")
    tu = metrics.get("accumulated_token_usage") or {}
    return Traj(tid or str(d.get("instance_id") or ""), sub, "openhands", steps, cost,
                tu.get("prompt_tokens"), tu.get("completion_tokens"), None, exit_status)


def parse_any(obj: dict, tid: str, sub: str) -> Traj | None:
    if not isinstance(obj, dict):
        return None
    t = parse_sweagent(obj, tid, sub) or parse_openhands(obj, tid, sub)
    if not t:
        for key, fmt in (("messages", "messages"), ("history", "messages"), ("steps", "messages"), ("trajectory", "messages")):
            if isinstance(obj.get(key), list) and obj[key] and isinstance(obj[key][0], dict) and "role" in obj[key][0]:
                t = parse_messages(obj[key], tid, sub, obj.get("info"), fmt)
                break
    if not t:
        return None
    model = obj.get("model_name") or obj.get("model")
    if model:
        t.submission = f"{sub}/{str(model).split('/')[-1][:40]}"
    for key in ("target", "resolved", "success"):
        v = obj.get(key)
        if isinstance(v, bool):
            t.resolved = v
            break
        if isinstance(v, (int, float)) and v in (0, 1):
            t.resolved = bool(v)
            break
    return t


def load_path(path: Path, sub: str, unparsed: list[str]) -> list[Traj]:
    out: list[Traj] = []
    if path.is_dir():
        for f in sorted(path.rglob("*")):
            if f.is_file() and f.suffix in (".traj", ".json", ".jsonl", ".md", ".yaml", ".yml", ".txt"):
                out += load_path(f, sub, unparsed)
        return out
    text = path.read_text(encoding="utf-8", errors="replace")
    tid = path.stem.replace(".traj", "")
    if path.suffix == ".jsonl":
        for i, line in enumerate(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = parse_any(obj, str(obj.get("instance_id") if isinstance(obj, dict) else "") or f"{tid}#{i}", sub)
            if t:
                out.append(t)
            else:
                unparsed.append(f"{path}#{i}")
        return out
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        unparsed.append(str(path))
        return out
    t = parse_any(obj, tid, sub)
    if t:
        out.append(t)
    else:
        unparsed.append(str(path))
    return out


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------
def price(t: Traj, pin: float, pout: float):
    if t.cost is not None and t.cost > 0:
        t.cost_source = "reported"
        return
    if t.tokens_in or t.tokens_out:
        t.cost = ((t.tokens_in or 0) * pin + (t.tokens_out or 0) * pout) / 1e6
        t.cost_source = "tokens"
        return
    # chars/4, with the naive "context re-sent every step" model: cumulative observation chars
    cum = 0
    tin = 0
    for s in t.steps:
        cum += len(s.action) + len(s.observation)
        tin += cum // 4
    tout = sum(max(s.response_len, len(s.action)) for s in t.steps) // 4
    t.tokens_in, t.tokens_out = tin, tout
    t.cost = (tin * pin + tout * pout) / 1e6
    t.cost_source = "chars"


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------
@dataclass
class Hit:
    detector: str
    traj_id: str
    submission: str
    wasted_steps: int
    wasted_cost: float
    note: str
    idx: set = field(default_factory=set)   # step indices this hit covers (for de-duplication across detectors)


def norm(a: str) -> str:
    return re.sub(r"\s+", " ", a.strip())


def detect(t: Traj, big_obs_chars: int) -> list[Hit]:
    hits: list[Hit] = []
    n = len(t.steps)
    if n == 0:
        return hits
    step_cost = (t.cost or 0) / n

    # T01 degenerate loop: identical action repeated with no state-changing action in between.
    # Chain length resets whenever an edit/write/install happens, so edit->test->edit->test is not a loop.
    chain = Counter()          # action -> repeats since last state change
    loop_idx = set()
    worst_a, worst_n = "", 0
    for i, s in enumerate(t.steps):
        a = norm(s.action)
        if not a:
            continue
        if STATE_CHANGE.search(a):
            chain.clear()
        chain[a] += 1
        if chain[a] >= 3:          # third+ identical call with nothing changed
            loop_idx.add(i)
        if chain[a] > worst_n:
            worst_a, worst_n = a, chain[a]
    if loop_idx:
        hits.append(Hit("T01 tool loop", t.id, t.submission, len(loop_idx), len(loop_idx) * step_cost,
                        f"'{worst_a[:60]}' ×{worst_n} with no state change between", loop_idx))

    # T02 identical retry immediately after an error observation
    retry_idx = set()
    for i in range(1, n):
        if norm(t.steps[i].action) == norm(t.steps[i - 1].action) and any(m in t.steps[i - 1].observation for m in ERROR_MARKERS):
            retry_idx.add(i)
    if retry_idx:
        hits.append(Hit("T02 identical retry", t.id, t.submission, len(retry_idx), len(retry_idx) * step_cost,
                        f"{len(retry_idx)} retries with unchanged input", retry_idx))

    # T03 context bloat: single observations above threshold (they get re-sent every later step)
    big = [(i, len(s.observation)) for i, s in enumerate(t.steps) if len(s.observation) > big_obs_chars]
    if big:
        # cost of dragging the excess through the remaining steps, chars/4 at the run's blended input price
        excess_tokens = sum((ln - big_obs_chars) // 4 * (n - i - 1) for i, ln in big)
        blended_in = (t.cost or 0) / max(t.tokens_in or 1, 1) if t.tokens_in else 0
        hits.append(Hit("T03 context bloat", t.id, t.submission, len(big), excess_tokens * blended_in,
                        f"{len(big)} observation(s) over {big_obs_chars:,} chars; largest {max(ln for _, ln in big):,}"))

    # T06 abandoned / T07 context exhausted (agent hit the context wall; harness may have force-submitted)
    ex = (t.exit_status or "").lower()
    clean_submit = ex in ("submitted", "success", "finished", "done") or \
                   (not ex and any(m in norm(t.steps[-1].action).lower() for m in SUBMIT_MARKERS))
    if "exit_context" in ex or "context" in ex:
        hits.append(Hit("T07 context exhausted", t.id, t.submission, n, t.cost or 0,
                        f"exit={t.exit_status}" + (" (forced submit)" if "submitted" in ex else " (no submit)"), set(range(n))))
    elif not clean_submit:
        hits.append(Hit("T06 abandoned", t.id, t.submission, n, t.cost or 0, f"exit={t.exit_status or 'unknown'}, no submit action", set(range(n))))

    # T13 edit thrash: same file edited many times
    files = Counter()
    for s in t.steps:
        m = re.search(r"(?:edit|str_replace_editor|open|create)[:\s]+([\w./\-]+\.\w+)", s.action) or \
            re.search(r'"path":\s*"([^"]+\.\w+)"', s.action)
        if m:
            files[m.group(1)] += 1
    thrash = {f for f, c in files.items() if c >= 6}
    if thrash:
        seen_f = Counter()
        th_idx = set()
        for i, s in enumerate(t.steps):
            m = re.search(r"(?:edit|str_replace_editor|open|create)[:\s]+([\w./\-]+\.\w+)", s.action)
            if m and m.group(1) in thrash:
                seen_f[m.group(1)] += 1
                if seen_f[m.group(1)] > 5:
                    th_idx.add(i)
        hits.append(Hit("T13 edit thrash", t.id, t.submission, len(th_idx), len(th_idx) * step_cost,
                        f"{sorted(thrash)[0]} edited {files[sorted(thrash)[0]]}×", th_idx))
    return hits


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def summarize(trajs: list[Traj], hits: list[Hit]) -> dict:
    by_sub = defaultdict(list)
    for t in trajs:
        by_sub[t.submission].append(t)
    hits_by_sub = defaultdict(list)
    for h in hits:
        hits_by_sub[h.submission].append(h)
    subs = {}
    for sub, ts in by_sub.items():
        costs = [t.cost or 0 for t in ts]
        steps = [len(t.steps) for t in ts]
        hs = hits_by_sub[sub]
        total = sum(costs)
        # de-duplicate: union of wasted step indices × step cost, plus non-step costs (T03), capped at run cost
        waste = 0.0        # mechanical: T01 T02 T03 T13
        sunk = 0.0         # runs that ended without a real result: T06 T07
        hs_by_traj = defaultdict(list)
        for h in hs:
            hs_by_traj[h.traj_id].append(h)
        SUNK = ("T06", "T07")
        for t in ts:
            th = hs_by_traj.get(t.id, [])
            if not th:
                continue
            mech = [h for h in th if not h.detector.startswith(SUNK)]
            idx = set().union(*[h.idx for h in mech]) if mech else set()
            step_cost = (t.cost or 0) / max(len(t.steps), 1)
            extra = sum(h.wasted_cost for h in mech if not h.idx)
            waste += min(len(idx) * step_cost + extra, t.cost or 0)
            if any(h.detector.startswith(SUNK) for h in th):
                sunk += (t.cost or 0)
        p90 = sorted(steps)[int(0.9 * (len(steps) - 1))] if steps else 0
        outliers = [t for t in ts if len(t.steps) > 2 * p90] if p90 else []
        det = defaultdict(lambda: {"trajs": 0, "cost": 0.0})
        for h in hs:
            det[h.detector]["trajs"] += 1
            det[h.detector]["cost"] += h.wasted_cost
        with_res = [t for t in ts if t.resolved is not None]
        flagged = {h.traj_id for h in hs}
        res_all = (sum(t.resolved for t in with_res) / len(with_res)) if with_res else None
        res_flag = [t.resolved for t in with_res if t.id in flagged]
        res_clean = [t.resolved for t in with_res if t.id not in flagged]
        subs[sub] = {
            "resolve_rate": res_all,
            "resolve_rate_with_findings": (sum(res_flag) / len(res_flag)) if res_flag else None,
            "resolve_rate_without_findings": (sum(res_clean) / len(res_clean)) if res_clean else None,
            "trajectories": len(ts),
            "cost_source": Counter(t.cost_source for t in ts).most_common(1)[0][0],
            "total_cost": total, "mean_cost": statistics.mean(costs) if costs else 0,
            "median_cost": statistics.median(costs) if costs else 0,
            "mean_steps": statistics.mean(steps) if steps else 0, "p90_steps": p90,
            "runs_over_2x_p90_steps": len(outliers),
            "trajs_with_any_finding": len({h.traj_id for h in hs}),
            "waste_cost": waste, "waste_share": (waste / total) if total else 0,
            "sunk_cost": sunk, "sunk_share": (sunk / total) if total else 0,
            "by_detector": {k: {"trajs": v["trajs"], "share_of_trajs": v["trajs"] / len(ts), "cost": v["cost"]} for k, v in sorted(det.items())},
            "worst": [{k: v for k, v in asdict(h).items() if k != "idx"} for h in sorted(hs, key=lambda h: -h.wasted_cost)[:5]],
        }
    total = sum(s["total_cost"] for s in subs.values())
    waste = sum(s["waste_cost"] for s in subs.values())
    sunk = sum(s["sunk_cost"] for s in subs.values())
    return {"submissions": subs, "trajectories": len(trajs), "total_cost": total, "waste_cost": waste,
            "waste_share": (waste / total) if total else 0, "sunk_cost": sunk, "sunk_share": (sunk / total) if total else 0}


def write(res: dict, unparsed: list[str], out: Path):
    out.mkdir(parents=True, exist_ok=True)
    (out / "trajectory-audit.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    L = ["# metermaid trajectory audit\n",
         f"{res['trajectories']:,} trajectories across {len(res['submissions'])} submission(s). "
         f"Total cost ${res['total_cost']:,.2f}. Mechanical waste ${res['waste_cost']:,.2f} ({res['waste_share']:.0%}) — "
         f"steps spent in identical-action loops, identical retries after errors, oversized tool output dragged through context, and edit thrash. "
         f"Separately, ${res['sunk_cost']:,.2f} ({res['sunk_share']:.0%}) was spent on runs that ended without a real result "
         f"(abandoned, or hit the context limit).\n",
         "Priced from each trajectory's own reported cost where present, else from tokens/chars at the --price defaults. "
         "Mechanical totals de-duplicate overlapping detectors and never exceed a run's cost; per-detector lines can overlap.\n",
         "| submission | trajs | cost basis | total $ | median $/run | mean steps | any finding | mechanical waste % | failed-run cost % |",
         "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for sub, s in sorted(res["submissions"].items(), key=lambda kv: -kv[1]["waste_cost"]):
        L.append(f"| {sub} | {s['trajectories']} | {s['cost_source']} | {s['total_cost']:,.2f} | {s['median_cost']:,.3f} | "
                 f"{s['mean_steps']:.0f} | {s['trajs_with_any_finding'] / s['trajectories']:.0%} | {s['waste_share']:.0%} | {s['sunk_share']:.0%} |")
    for sub, s in sorted(res["submissions"].items(), key=lambda kv: -kv[1]["waste_cost"]):
        L.append(f"\n## {sub}\n")
        for d, v in s["by_detector"].items():
            L.append(f"- {d}: {v['share_of_trajs']:.0%} of runs, ${v['cost']:,.2f}")
        L.append(f"- runs over 2× the p90 step count: {s['runs_over_2x_p90_steps']}")
        if s["resolve_rate"] is not None:
            rf = s["resolve_rate_with_findings"]; rc = s["resolve_rate_without_findings"]
            L.append(f"- resolve rate: {s['resolve_rate']:.0%} overall; "
                     f"{rf:.0%} for runs with findings" if rf is not None else "- resolve rate: n/a")
            if rc is not None:
                L[-1] += f", {rc:.0%} for clean runs"
        if s["worst"]:
            L.append("\nWorst runs:")
            for h in s["worst"]:
                L.append(f"- {h['traj_id']}: {h['detector']} — ${h['wasted_cost']:,.2f}, {h['wasted_steps']} steps, {h['note']}")
    if unparsed:
        L.append(f"\n## Unparsed files ({len(unparsed)})\n")
        L += [f"- {u}" for u in unparsed[:30]]
    (out / "trajectory-audit.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"\nWrote {out / 'trajectory-audit.md'} and {out / 'trajectory-audit.json'}")


# ---------------------------------------------------------------------------
def demo() -> list[Traj]:
    import random
    random.seed(3)
    ts = []
    for i in range(40):
        steps = []
        n = random.randint(12, 60)
        for k in range(n):
            a = random.choice(["ls -R src", "cat src/app.py", "python -m pytest tests/test_x.py", "grep -rn foo src",
                               "edit src/app.py", "python reproduce.py"])
            obs = "ok" if random.random() > 0.3 else "Traceback (most recent call last):\n  File ... Error: boom"
            if i % 7 == 0 and 5 < k < 12:
                a, obs = "python reproduce.py", "Traceback (most recent call last): Error: still broken"   # loop + retries
            if i % 11 == 0 and k == 3:
                obs = "x" * 90_000                                                                         # bloat
            steps.append(Step(a, obs, 200))
        if i % 5:
            steps.append(Step("submit", "", 50))
        t = Traj(f"repo__repo-{1000 + i}", "demo_sweagent_claude", "sweagent", steps,
                 cost=round(0.02 * len(steps) * random.uniform(0.6, 1.6), 3), tokens_in=len(steps) * 6000,
                 tokens_out=len(steps) * 300, api_calls=len(steps), exit_status="submitted" if i % 5 else "exit_cost")
        ts.append(t)
    return ts


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--out", default="./traj-audit")
    ap.add_argument("--label-by-parent", action="store_true", help="submission label = parent folder of each file's trajs dir")
    ap.add_argument("--price-in", type=float, default=3.0, help="USD per 1M input tokens when no cost is reported")
    ap.add_argument("--price-out", type=float, default=15.0, help="USD per 1M output tokens when no cost is reported")
    ap.add_argument("--big-obs-chars", type=int, default=20_000)
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    unparsed: list[str] = []
    if a.demo:
        trajs = demo()
    else:
        if not a.paths:
            sys.exit("give one or more paths, or --demo")
        trajs = []
        for p in a.paths:
            P = Path(p)
            if a.label_by_parent and P.is_dir():
                for f in sorted(P.rglob("*")):
                    if f.is_file():
                        sub = f.parent.parent.name if f.parent.name == "trajs" else f.parent.name
                        trajs += load_path(f, sub, unparsed)
            else:
                trajs += load_path(P, P.name if P.is_dir() else P.parent.name, unparsed)
    if not trajs:
        sys.exit(f"no trajectories parsed ({len(unparsed)} files skipped)")
    for t in trajs:
        price(t, a.price_in, a.price_out)
    hits = [h for t in trajs for h in detect(t, a.big_obs_chars)]
    write(summarize(trajs, hits), unparsed, Path(a.out))


if __name__ == "__main__":
    main()
