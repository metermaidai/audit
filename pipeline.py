#!/usr/bin/env python3
"""
pipeline.py — the scaled trajectory pipeline.

    python -m pip install datasets pyarrow duckdb
    python pipeline.py sweep --limit 20000            # every registered dataset/config/split -> data/runs/*.parquet
    python pipeline.py ingest nvidia/Open-SWE-Traces --config v1.1 --split sweagent --limit 5000
    python pipeline.py report                          # DuckDB over data/runs -> report/index.md + index.json
    python pipeline.py ingest-json samples/*.json      # parse raw sample rows (testing new formats)

Rows stream from Hugging Face and are parsed in-process; nothing is written per run. Each run becomes one
row in a Parquet file with its detector features. Steps are kept only when --steps is passed.
"""
from __future__ import annotations
import argparse, ast, glob, json, re, statistics, sys
from collections import Counter
from dataclasses import dataclass, asdict, field
from pathlib import Path

ERROR_MARKERS = ("Traceback", "Error:", "error:", "ERROR", "not found", "No such file", "command not found",
                 "SyntaxError", "failed", "FAILED", "Permission denied", "Exception", "exit code 1", "returned non-zero")
TERMINAL_TOOLS = ("submit", "finish", "complete", "done", "final_answer", "task_complete")
FINAL_MARKERS = re.compile(r"(MINI_SWE_AGENT_FINAL_OUTPUT|COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT)")
STATE_CHANGE = re.compile(r"(str_replace|\bedit\b|\bcreate\b|\bwrite\b|\binsert\b|\bappend\b|\brm\b|\bmv\b|\bcp\b|sed -i|\btouch\b|"
                          r"\bmkdir\b|\bpatch\b|pip install|npm install|git (apply|checkout|stash|reset|commit)|\becho\b[^|]*>|"
                          r"\bcat\b[^|]*>|new_str|file_text|\"command\": \"(create|str_replace|insert|undo_edit)\"|"
                          r"<parameter=command>(create|str_replace|insert)|str_replace_editor (create|str_replace|insert)|"
                          r"keystrokes.*(>|sed -i|rm |mv |cp ))", re.I | re.S)
PRICE_IN, PRICE_OUT = 3.0, 15.0     # USD per 1M tokens for the chars/4 estimate; percentages are what we quote

# ---------------------------------------------------------------------------
# Registry: how to read each dataset. Anything not listed here is handled generically.
# ---------------------------------------------------------------------------
REGISTRY = {
    "nebius/SWE-agent-trajectories":            dict(field="trajectory", model="col:model_name", resolved="col:target", exit="col:exit_status", scaffold="swe-agent"),
    "SWE-bench/SWE-smith-trajectories":         dict(field="messages", model="col:model", resolved="col:resolved", scaffold="swe-agent/{split}", splits=["tool", "xml", "ticks"]),
    "nebius/SWE-rebench-openhands-trajectories": dict(field="trajectory", model="Qwen3-Coder-480B", resolved="col:resolved", exit="col:exit_status", scaffold="openhands"),
    "nvidia/Open-SWE-Traces":                   dict(field="auto", model="cfgmap", resolved="auto", scaffold="{split}", configs=["v1.0", "v1.1", "v1.2"], splits="all",
                                                     model_by_config={"v1.0": "MiniMax-M2.5 + Qwen3.5-122B (mixed)", "v1.1": "DeepSeek-V4-Flash + Qwen3.6-27B (mixed)", "v1.2": "Qwen3.8-27B"}),
    "nvidia/SWE-Hero-openhands-trajectories":   dict(field="trajectory", model="Qwen3-Coder-480B", resolved="none", scaffold="openhands"),
    "nvidia/SWE-Zero-openhands-trajectories":   dict(field="trajectory", model="Qwen3-Coder-480B", resolved="none", scaffold="openhands"),
    "thoughtworks/agentic-coding-trajectories": dict(field="messages_json", model="col:source_dataset", resolved="json:ground_truth_meta_json.resolved", scaffold="col:agent_framework"),
    "SWE-Gym/OpenHands-Sampled-Trajectories":   dict(field="messages", model="runid:run_id", resolved="col:resolved", scaffold="openhands"),
    "open-thoughts/AgentTrove":                 dict(field="conversations", model="col:model", resolved="col:result", scaffold="col:agent"),
    "ricdomolm/mini-coder-trajs-400k":          dict(field="messages", model="col:model", resolved="col:verified", scaffold="mini-swe-agent"),
    "AlienKevin/SWE-ZERO-12M-trajectories":     dict(field="messages", model="mini-coder-1.7B", resolved="none", exit="col:exit_status", scaffold="col:trajectory_format"),
}


# ---------------------------------------------------------------------------
@dataclass
class Step:
    action: str
    tool: str          # tool/command family
    obs: str
    is_call: bool      # came from a structured/fenced call (vs. plain text)
    terminal: bool     # submit/finish/task_complete


@dataclass
class Run:
    dataset: str; config: str; split: str; run_id: str; model: str; scaffold: str
    resolved: bool | None; exit_status: str | None
    steps: int; calls: int; est_tokens_in: int; est_tokens_out: int; est_cost: float
    terminal: str                  # submitted | text_end | context_exhausted | incomplete | cutoff | unknown
    loop_steps: int; loop_worst: int; loop_worst_action: str
    retry_steps: int; bloat_obs: int; bloat_excess_tokens: int; thrash_steps: int
    mech_waste_steps: int; mech_waste_cost: float; sunk: bool; any_finding: bool


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def _as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("[") or s.startswith("{"):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                try:
                    return ast.literal_eval(s)
                except Exception:
                    return None
    return None


def _tool_calls(m: dict):
    for k in ("tool_calls", "tool_calls_json"):
        v = m.get(k)
        if v in (None, "", "None", "null"):
            continue
        lst = _as_list(v)
        if isinstance(lst, list) and lst:
            out = []
            for tc in lst:
                if not isinstance(tc, dict):
                    continue
                fn = tc.get("function", tc)
                name = fn.get("name") or tc.get("name") or ""
                args = fn.get("arguments", fn.get("input", ""))
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        pass
                out.append((name, args))
            if out:
                return out
    return []


def _content_text(content):
    """Flatten content; return (text, tool_uses, tool_results)."""
    tool_uses, tool_results, texts = [], [], []
    if isinstance(content, list):
        for c in content:
            if not isinstance(c, dict):
                texts.append(str(c)); continue
            ct = c.get("type")
            if ct == "tool_use":
                tool_uses.append((c.get("name") or "", c.get("input")))
            elif ct == "tool_result":
                rc = c.get("content")
                if isinstance(rc, list):
                    rc = " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in rc)
                tool_results.append(str(rc or ""))
            else:
                texts.append(str(c.get("text") or c.get("content") or ""))
    elif content is not None and content != "None":
        texts.append(str(content))
    return " ".join(texts + tool_results), tool_uses, tool_results


XML_FN = re.compile(r"<function=([^>\s]+)>(.*?)</function>", re.S)
XML_PARAM = re.compile(r"<parameter=([^>\s]+)>(.*?)</parameter>", re.S)
FENCE = re.compile(r"```(?:\w+)?\s*\n(.*?)```", re.S)


def actions_from_text(text: str) -> list[tuple[str, object]]:
    """Return [(tool, args)] extracted from free text: XML function calls, fenced blocks, terminus JSON."""
    out = []
    for name, body in XML_FN.findall(text):
        params = {k: v.strip() for k, v in XML_PARAM.findall(body)}
        out.append((name, params or body.strip()))
    if out:
        return out
    s = text.strip()
    if s.startswith("{") and '"commands"' in s or s.startswith("{") and "task_complete" in s:
        try:
            j = json.loads(s)
            cmds = j.get("commands") or []
            keys = "\n".join(str(c.get("keystrokes", "")) for c in cmds if isinstance(c, dict))
            tool = "task_complete" if j.get("task_complete") is True else "terminal"
            return [(tool, keys or "<no commands>")]
        except Exception:
            pass
    for block in FENCE.findall(text):
        b = block.strip()
        if b:
            first = b.split()[0] if b.split() else ""
            out.append((first, b))
    return out


def norm_action(tool: str, args) -> str:
    if isinstance(args, (dict, list)):
        args = json.dumps(args, sort_keys=True, default=str)
    return re.sub(r"\s+", " ", f"{tool} {args}".strip())


def parse_messages(msgs: list) -> list[Step]:
    steps: list[Step] = []
    pending: list[tuple[str, str, bool]] | None = None   # (action, tool, terminal)
    pending_is_call = False
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").lower()
        role = {"ai": "assistant", "agent": "assistant", "model": "assistant", "human": "user",
                "tool_result": "tool", "function": "tool", "environment": "tool"}.get(role, role)
        content = m.get("content")
        if content is None:
            content = m.get("text") if m.get("text") is not None else m.get("message")
        text, tool_uses, tool_results = _content_text(content)
        if tool_results and role == "user":
            role = "tool"
        if role == "assistant":
            if pending is not None:
                for a, tl, term in pending:
                    steps.append(Step(a, tl, "", pending_is_call, term))
            calls = _tool_calls(m) or tool_uses or actions_from_text(text)
            is_call = bool(_tool_calls(m) or tool_uses or actions_from_text(text))
            if not calls:
                # text-only assistant turn: treat as a terminal-ish narration step
                last = [l for l in text.strip().splitlines() if l.strip()]
                calls = [("text", f"turn{len(steps) + (len(pending) if pending else 0)}")]   # unique per turn: narration is never a loop
            pending = []
            for tool, args in calls:
                tl = str(tool).split("/")[-1]
                a = norm_action(tl, args)
                term = any(k in tl.lower() for k in TERMINAL_TOOLS) or FINAL_MARKERS.search(a) is not None
                pending.append((a, tl, term))
            pending_is_call = is_call
        elif role in ("user", "tool") and pending is not None:
            for i, (a, tl, term) in enumerate(pending):
                steps.append(Step(a, tl, text if i == 0 else "", pending_is_call, term))
            pending = None
    if pending is not None:
        for a, tl, term in pending:
            steps.append(Step(a, tl, "", pending_is_call, term))
    return steps


def parse_sweagent_struct(traj: list) -> list[Step]:
    steps = []
    for t in traj:
        if not isinstance(t, dict):
            continue
        a = str(t.get("action") or "")
        tl = a.split()[0] if a.split() else ""
        steps.append(Step(norm_action(tl, a[len(tl):].strip()), tl, str(t.get("observation") or ""), True,
                          tl.lower() in TERMINAL_TOOLS))
    return steps


def parse_openhands_events(hist: list) -> list[Step]:
    steps, pending = [], None
    for ev in hist:
        if not isinstance(ev, dict):
            continue
        if ev.get("action") and ev.get("source") == "agent":
            args = ev.get("args") or {}
            act = str(ev["action"])
            key = args.get("command") or args.get("code") or args.get("path") or ev.get("message") or ""
            pending = (norm_action(act, {"k": key, "p": args.get("path", ""), "c": args.get("command", "")}), act,
                       act.lower() in ("finish", "agentfinishaction"))
        elif ev.get("observation") is not None and pending is not None:
            steps.append(Step(pending[0], pending[1], str(ev.get("content") or ""), True, pending[2]))
            pending = None
    if pending:
        steps.append(Step(pending[0], pending[1], "", True, pending[2]))
    return steps


def steps_from_row(row: dict, field: str) -> tuple[list[Step], str]:
    if field == "auto":
        for f in ("trajectory", "messages", "messages_json", "conversations", "history", "steps"):
            if row.get(f) not in (None, "", "None"):
                field = f
                break
    v = _as_list(row.get(field))
    if not isinstance(v, list) or not v:
        return [], field
    first = v[0] if isinstance(v[0], dict) else {}
    if "action" in first and "observation" in first:
        return parse_sweagent_struct(v), field
    if "source" in first and ("action" in first or "observation" in first):
        return parse_openhands_events(v), field
    return parse_messages(v), field


# ---------------------------------------------------------------------------
# Metadata resolution
# ---------------------------------------------------------------------------
def resolve_meta(row: dict, spec: str | None, split: str, default: str = "unknown") -> str | None:
    if spec is None or spec == "none":
        return None
    if spec.startswith("col:"):
        v = row.get(spec[4:])
        return None if v in (None, "", "None") else str(v)
    if spec.startswith("json:"):
        col, key = spec[5:].split(".", 1)
        try:
            j = row.get(col)
            j = json.loads(j) if isinstance(j, str) else (j or {})
            v = j.get(key)
            return None if v is None else str(v)
        except Exception:
            return None
    if spec.startswith("runid:"):
        v = str(row.get(spec[6:]) or "")
        m = re.match(r"([A-Za-z0-9.\-]+?)(?:_maxiter|_N_|__|$)", v)
        return m.group(1) if m else (v or None)
    if spec == "auto":
        for k in ("model_name", "model", "recorded_model", "llm", "agent_model"):
            if row.get(k) not in (None, "", "None"):
                return str(row[k])
        for k in ("split_name",):
            pass
        return default
    return spec.format(split=split)


def to_bool(v) -> bool | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("true", "1", "1.0", "yes", "resolved", "pass", "passed", "success"):
        return True
    if s in ("false", "0", "0.0", "no", "unresolved", "fail", "failed", "none", ""):
        return False if s != "none" and s != "" else None
    return None


# ---------------------------------------------------------------------------
# Detection at ingest
# ---------------------------------------------------------------------------
def analyze_run(steps: list[Step], exit_status: str | None, big_obs_chars: int = 20_000):
    n = len(steps)
    # cost estimate: cumulative context re-sent each step, chars/4
    cum = tin = tout = 0
    for s in steps:
        cum += len(s.action) + len(s.obs)
        tin += cum // 4
        tout += max(len(s.action), 40) // 4
    cost = (tin * PRICE_IN + tout * PRICE_OUT) / 1e6
    step_cost = cost / n if n else 0

    chain = Counter(); loop_idx = set(); worst_a, worst_n = "", 0
    for i, s in enumerate(steps):
        if not s.action:
            continue
        if STATE_CHANGE.search(s.action):
            chain.clear()
        chain[s.action] += 1
        if chain[s.action] >= 3:
            loop_idx.add(i)
        if chain[s.action] > worst_n:
            worst_a, worst_n = s.action, chain[s.action]

    retry_idx = set()
    for i in range(1, n):
        prev = steps[i - 1]
        err = any(m in prev.obs for m in ERROR_MARKERS) or re.search(r"<returncode>[1-9]", prev.obs) is not None
        if steps[i].action == prev.action and err and steps[i].is_call:
            retry_idx.add(i)

    big = [(i, len(s.obs)) for i, s in enumerate(steps) if len(s.obs) > big_obs_chars]
    bloat_tokens = sum((ln - big_obs_chars) // 4 * (n - i - 1) for i, ln in big)

    files = Counter(); th_idx = set(); seen = Counter()
    for i, s in enumerate(steps):
        m = re.search(r'"path": "([^"]+\.\w+)"', s.action) or re.search(r"(?:edit|open|create|str_replace_editor \w+)\s+([\w./\-]+\.\w+)", s.action)
        if m and STATE_CHANGE.search(s.action):
            files[m.group(1)] += 1
    thrash = {f for f, c in files.items() if c >= 6}
    for i, s in enumerate(steps):
        m = re.search(r'"path": "([^"]+\.\w+)"', s.action) or re.search(r"(?:edit|open|create|str_replace_editor \w+)\s+([\w./\-]+\.\w+)", s.action)
        if m and m.group(1) in thrash and STATE_CHANGE.search(s.action):
            seen[m.group(1)] += 1
            if seen[m.group(1)] > 5:
                th_idx.add(i)

    # terminal classification
    ex = (exit_status or "").lower()
    if "context" in ex:
        terminal = "context_exhausted"
    elif ex in ("submitted", "submit", "success", "finished", "done"):
        terminal = "submitted"
    elif ex and any(k in ex for k in ("incomplete", "cost", "error", "max", "limit", "timeout", "unknown_error")):
        terminal = "incomplete"
    elif n and steps[-1].terminal:
        terminal = "submitted"
    elif n and not steps[-1].is_call:
        terminal = "text_end"          # agent stopped with a message (OpenHands style finish)
    elif n and steps[-1].is_call and not steps[-1].obs:
        terminal = "cutoff"            # last thing was a call with no observation: run was cut
    else:
        terminal = "unknown" if not n else "cutoff"

    mech_idx = loop_idx | retry_idx            # edit thrash is reported separately; it flags normal iterative editing too often
    mech_cost = min(len(mech_idx) * step_cost + bloat_tokens * PRICE_IN / 1e6, cost)
    return dict(steps=n, calls=sum(1 for s in steps if s.is_call), est_tokens_in=tin, est_tokens_out=tout, est_cost=cost,
                terminal=terminal, loop_steps=len(loop_idx), loop_worst=worst_n, loop_worst_action=worst_a[:120],
                retry_steps=len(retry_idx), bloat_obs=len(big), bloat_excess_tokens=bloat_tokens, thrash_steps=len(th_idx),
                mech_waste_steps=len(mech_idx), mech_waste_cost=mech_cost,
                sunk=terminal in ("context_exhausted", "incomplete", "cutoff"),
                any_finding=bool(mech_idx or big or terminal in ("context_exhausted", "incomplete", "cutoff")))


def row_to_run(row: dict, ds: str, cfg: str, split: str, spec: dict, idx: int) -> Run | None:
    steps, field = steps_from_row(row, spec.get("field", "auto"))
    if not steps:
        return None
    if spec.get("model") == "cfgmap":
        model = resolve_meta(row, "auto", split, default="") or spec.get("model_by_config", {}).get(cfg, f"{ds.split('/')[-1]}/{cfg}")
    else:
        model = resolve_meta(row, spec.get("model", "auto"), split, default=f"{ds.split('/')[-1]}") or "unknown"
    scaffold = resolve_meta(row, spec.get("scaffold", "unknown"), split) or "unknown"
    resolved = to_bool(resolve_meta(row, spec.get("resolved", "auto"), split)) if spec.get("resolved", "auto") != "auto" else \
               next((to_bool(row.get(k)) for k in ("resolved", "target", "verified", "success", "result") if row.get(k) is not None), None)
    exit_status = resolve_meta(row, spec.get("exit"), split) if spec.get("exit") else (str(row["exit_status"]) if row.get("exit_status") not in (None, "None") else None)
    rid = next((str(row[k]) for k in ("traj_id", "trajectory_id", "run_id", "session_id", "instance_id", "id") if row.get(k)), f"row{idx}")
    feats = analyze_run(steps, exit_status)
    return Run(dataset=ds, config=cfg or "default", split=split, run_id=f"{rid}#{idx}", model=str(model)[:80], scaffold=str(scaffold)[:60],
               resolved=resolved, exit_status=exit_status, **feats)


# ---------------------------------------------------------------------------
# Ingest / sweep / report
# ---------------------------------------------------------------------------
def write_parquet(runs: list[Run], path: Path):
    import pyarrow as pa, pyarrow.parquet as pq
    path.parent.mkdir(parents=True, exist_ok=True)
    tbl = pa.Table.from_pylist([asdict(r) for r in runs])
    pq.write_table(tbl, path)


def ingest(ds: str, cfg: str | None, split: str, limit: int, out: Path) -> int:
    from datasets import load_dataset
    spec = REGISTRY.get(ds, {})
    print(f"=== {ds} config={cfg or 'default'} split={split} limit={limit}", file=sys.stderr)
    it = iter(load_dataset(ds, cfg, split=split, streaming=True))
    runs, n, bad = [], 0, 0
    for i, row in enumerate(it):
        if i >= limit:
            break
        try:
            r = row_to_run(row, ds, cfg or "default", split, spec, i)
        except Exception as e:
            bad += 1
            if bad <= 3:
                print(f"  row {i} failed: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            continue
        if r:
            runs.append(r); n += 1
        else:
            bad += 1
        if (i + 1) % 1000 == 0:
            print(f"  {i + 1} rows, {n} parsed", file=sys.stderr)
    tag = f"{ds.replace('/', '__')}__{cfg or 'default'}__{split}"
    if runs:
        write_parquet(runs, out / "runs" / f"{tag}.parquet")
    print(f"  done: {n} runs parsed, {bad} skipped -> {tag}.parquet", file=sys.stderr)
    return n


def sweep(limit: int, out: Path, only: list[str] | None):
    from datasets import get_dataset_split_names, get_dataset_config_names
    for ds, spec in REGISTRY.items():
        if only and ds not in only:
            continue
        configs = spec.get("configs") or [None]
        for cfg in configs:
            splits = spec.get("splits") or "all"
            if splits == "all":
                try:
                    splits = get_dataset_split_names(ds, cfg)
                except Exception as e:
                    print(f"  could not list splits for {ds}/{cfg}: {str(e)[:120]}", file=sys.stderr)
                    splits = ["train"]
            for sp in splits:
                try:
                    ingest(ds, cfg, sp, limit, out)
                except Exception as e:
                    print(f"  FAILED {ds}/{cfg}/{sp}: {type(e).__name__}: {str(e)[:200]}", file=sys.stderr)


def ingest_json(paths: list[str], out: Path):
    """Parse raw sample rows (as written by hf_batch --sample) for testing new formats."""
    runs = []
    for p in paths:
        rows = json.load(open(p, encoding="utf-8"))
        name = Path(p).stem
        parts = name.split("__")
        ds = "/".join(parts[:2]) if len(parts) >= 2 else name
        cfg = parts[2] if len(parts) > 3 else "default"
        split = parts[-1].replace(".raw", "")
        spec = REGISTRY.get(ds, {})
        for i, row in enumerate(rows):
            if "_error" in row:
                continue
            r = row_to_run(row, ds, cfg, split, spec, i)
            print(f"{name}: {'OK ' if r else 'NO '} " + (f"model={r.model} scaffold={r.scaffold} steps={r.steps} calls={r.calls} terminal={r.terminal} resolved={r.resolved} loops={r.loop_steps} retries={r.retry_steps} bloat={r.bloat_obs}" if r else ""))
            if r:
                runs.append(r)
    if runs:
        write_parquet(runs, out / "runs" / "samples.parquet")


def report(data: Path, out: Path):
    import duckdb
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"""CREATE VIEW runs AS
        SELECT * REPLACE (
               CASE WHEN dataset = 'nvidia/Open-SWE-Traces' AND config = 'v1.0' THEN 'MiniMax-M2.5 + Qwen3.5-122B (mixed)'
                    WHEN dataset = 'nvidia/Open-SWE-Traces' AND config = 'v1.1' THEN 'DeepSeek-V4-Flash + Qwen3.6-27B (mixed)'
                    WHEN dataset = 'nvidia/Open-SWE-Traces' AND config = 'v1.2' THEN 'Qwen3.8-27B'
                    ELSE model END AS model),
               least((loop_steps + retry_steps) * est_cost / greatest(steps, 1) + bloat_excess_tokens * {PRICE_IN} / 1e6, est_cost) AS mech_cost,
               (loop_steps > 0 OR retry_steps > 0 OR bloat_obs > 0 OR sunk) AS flagged,
               ((2.0 * est_tokens_in / (steps + 1)) * {PRICE_IN} + (est_tokens_in - 2.0 * est_tokens_in / (steps + 1)) * {PRICE_IN} * 0.1 + est_tokens_out * {PRICE_OUT}) / 1e6 AS est_cost_cached
        FROM read_parquet('{(data / 'runs').as_posix()}/*.parquet', union_by_name=true)""")
    q = """
    SELECT dataset, config, split, model, scaffold,
           count(*) AS runs,
           avg(steps) AS mean_steps,
           quantile_cont(steps, 0.5) AS median_steps,
           sum(est_cost) AS est_cost,
           sum(mech_cost) / nullif(sum(est_cost), 0) AS mech_share,
           sum(CASE WHEN sunk THEN est_cost ELSE 0 END) / nullif(sum(est_cost), 0) AS sunk_share,
           avg(CASE WHEN loop_steps > 0 THEN 1 ELSE 0 END) AS loop_rate,
           avg(CASE WHEN retry_steps > 0 THEN 1 ELSE 0 END) AS retry_rate,
           avg(CASE WHEN bloat_obs > 0 THEN 1 ELSE 0 END) AS bloat_rate,
           avg(CASE WHEN terminal = 'context_exhausted' THEN 1 ELSE 0 END) AS ctx_rate,
           avg(CASE WHEN sunk THEN 1 ELSE 0 END) AS sunk_rate,
           avg(CASE WHEN flagged THEN 1 ELSE 0 END) AS finding_rate,
           avg(CASE WHEN thrash_steps > 0 THEN 1 ELSE 0 END) AS thrash_rate,
           avg(CAST(resolved AS INT)) AS resolve,
           avg(CASE WHEN flagged THEN CAST(resolved AS INT) END) AS resolve_flag,
           avg(CASE WHEN NOT flagged THEN CAST(resolved AS INT) END) AS resolve_clean,
           avg(CASE WHEN loop_steps > 0 THEN CAST(resolved AS INT) END) AS resolve_loop,
           avg(CASE WHEN retry_steps > 0 THEN CAST(resolved AS INT) END) AS resolve_retry,
           avg(CASE WHEN bloat_obs > 0 THEN CAST(resolved AS INT) END) AS resolve_bloat,
           avg(CASE WHEN bloat_obs = 0 THEN CAST(resolved AS INT) END) AS resolve_nobloat,
           avg(CASE WHEN sunk THEN CAST(resolved AS INT) END) AS resolve_sunk,
           count(resolved) AS n_resolved_known,
           mode(terminal) AS top_terminal
    FROM runs GROUP BY ALL ORDER BY runs DESC"""
    rows = con.execute(q).fetchall()
    cols = [d[0] for d in con.description]
    recs = [dict(zip(cols, r)) for r in rows]

    # step-count-controlled resolve gap: within step deciles, flagged vs clean
    q2 = """
    WITH b AS (SELECT *, ntile(5) OVER (PARTITION BY dataset, model ORDER BY steps) AS step_bucket FROM runs WHERE resolved IS NOT NULL)
    SELECT dataset, model, step_bucket,
           count(*) AS n,
           avg(CASE WHEN flagged THEN 1 ELSE 0 END) AS finding_rate,
           avg(CASE WHEN flagged THEN CAST(resolved AS INT) END) AS resolve_flag,
           avg(CASE WHEN NOT flagged THEN CAST(resolved AS INT) END) AS resolve_clean,
           avg(CASE WHEN bloat_obs > 0 THEN CAST(resolved AS INT) END) AS resolve_bloat,
           avg(CASE WHEN bloat_obs = 0 THEN CAST(resolved AS INT) END) AS resolve_nobloat
    FROM b GROUP BY ALL HAVING count(*) >= 50 ORDER BY dataset, model, step_bucket"""
    q3 = """
    WITH b AS (SELECT *, ntile(5) OVER (PARTITION BY dataset, config, split, model ORDER BY steps) AS q FROM runs),
         t AS (SELECT dataset, config, split, model, sum(est_cost) AS total, sum(est_cost_cached) AS total_c, count(*) AS n FROM b GROUP BY ALL)
    SELECT b.dataset, b.config, b.split, b.model, q,
           count(*) AS n, min(steps) AS steps_lo, max(steps) AS steps_hi,
           sum(est_cost) / any_value(t.total) AS cost_share,
           sum(est_cost_cached) / any_value(t.total_c) AS cost_share_cached,
           avg(CAST(resolved AS INT)) AS resolve,
           sum(CAST(resolved AS INT)) / nullif(sum(est_cost), 0) AS resolved_per_dollar
    FROM b JOIN t USING (dataset, config, split, model)
    GROUP BY ALL HAVING count(*) >= 200 ORDER BY dataset, config, split, model, q"""
    marg = [dict(zip([d[0] for d in con.description], r)) for r in con.execute(q3).fetchall()]
    exits = [dict(zip(["dataset", "model", "terminal", "exit_status", "n"], r)) for r in con.execute(
        "SELECT dataset, model, terminal, coalesce(exit_status,'') , count(*) FROM runs GROUP BY ALL ORDER BY dataset, model, 5 DESC").fetchall()]
    strat = [dict(zip([d[0] for d in con.description], r)) for r in con.execute(q2).fetchall()]
    total = con.execute("SELECT count(*), sum(est_cost), sum(mech_cost), sum(CASE WHEN sunk THEN est_cost END) FROM runs").fetchone()

    (out / "index.json").write_text(json.dumps({"total_runs": total[0], "groups": recs, "stratified": strat, "marginal": marg, "exits": exits}, indent=1, default=str), encoding="utf-8")
    pct = lambda v: "—" if v is None else f"{v:.0%}"
    L = ["# Agent Waste Index\n",
         f"{total[0]:,} runs. Estimated cost basis: chars/4 at Sonnet-class rates — quote percentages, not dollars. "
         f"Mechanical waste {total[2] / total[1]:.0%} of estimated spend; {total[3] / total[1]:.0%} spent on runs that ended without a result.\n",
         "| dataset | config/split | model | scaffold | runs | med steps | loops | blind retries | big tool output | edit thrash | ctx exhausted | ended w/o result | mech waste % | failed-run % | resolve | w/ finding | clean | w/ big output | w/o big output |",
         "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in recs:
        L.append(f"| {r['dataset'].split('/')[-1]} | {r['config']}/{r['split']} | {r['model'][:40]} | {r['scaffold'][:24]} | {r['runs']:,} | {r['median_steps']:.0f} | "
                 f"{pct(r['loop_rate'])} | {pct(r['retry_rate'])} | {pct(r['bloat_rate'])} | {pct(r['thrash_rate'])} | {pct(r['ctx_rate'])} | {pct(r['sunk_rate'])} | "
                 f"{pct(r['mech_share'])} | {pct(r['sunk_share'])} | {pct(r['resolve'])} | {pct(r['resolve_flag'])} | {pct(r['resolve_clean'])} | {pct(r['resolve_bloat'])} | {pct(r['resolve_nobloat'])} |")
    L.append("\n## Resolve gap controlled for run length\n")
    L.append("Within each dataset/model, runs are split into five buckets by step count. If waste only proxied for hard tasks, the flagged/clean gap would vanish inside buckets.\n")
    L.append("| dataset | model | step bucket | n | finding rate | resolve w/ finding | resolve clean | resolve w/ big output | resolve w/o big output |")
    L.append("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for s in strat:
        L.append(f"| {s['dataset'].split('/')[-1]} | {s['model'][:40]} | {s['step_bucket']} | {s['n']:,} | {pct(s['finding_rate'])} | {pct(s['resolve_flag'])} | {pct(s['resolve_clean'])} | {pct(s['resolve_bloat'])} | {pct(s['resolve_nobloat'])} |")
    L.append("\n## Where the money goes: cost and resolve rate by run-length quintile\n")
    L.append("Runs are split into five equal-count buckets by step count within each group. Cost share is the bucket's share of the group's estimated spend; resolved/$ is resolved tasks per estimated dollar (relative within a group).\n")
    L.append("| dataset | config/split | model | quintile | steps | cost share (no cache) | cost share (cached reads) | resolve | resolved per $ |")
    L.append("|---|---|---|---:|---|---:|---:|---:|---:|")
    for m in marg:
        rpd = "—" if m["resolved_per_dollar"] is None else f"{m['resolved_per_dollar']:.2f}"
        L.append(f"| {m['dataset'].split('/')[-1]} | {m['config']}/{m['split']} | {m['model'][:36]} | {m['q']} | {m['steps_lo']}–{m['steps_hi']} | {pct(m['cost_share'])} | {pct(m['cost_share_cached'])} | {pct(m['resolve'])} | {rpd} |")
    L.append("\n## How runs ended (sanity check on end-of-run classification)\n")
    L.append("| dataset | model | terminal | exit_status | n |")
    L.append("|---|---|---|---|---:|")
    for e in exits[:120]:
        L.append(f"| {e['dataset'].split('/')[-1]} | {e['model'][:40]} | {e['terminal']} | {e['exit_status'][:40]} | {e['n']:,} |")
    (out / "index.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[:4 + len(recs)]))
    print(f"\nWrote {out / 'index.md'} and {out / 'index.json'}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest"); p.add_argument("dataset"); p.add_argument("--config"); p.add_argument("--split", default="train"); p.add_argument("--limit", type=int, default=5000); p.add_argument("--out", default="data")
    p = sub.add_parser("sweep"); p.add_argument("--limit", type=int, default=20000); p.add_argument("--only", nargs="*"); p.add_argument("--out", default="data")
    p = sub.add_parser("report"); p.add_argument("--data", default="data"); p.add_argument("--out", default="report")
    p = sub.add_parser("ingest-json"); p.add_argument("paths", nargs="+"); p.add_argument("--out", default="data")
    a = ap.parse_args()
    if a.cmd == "ingest":
        ingest(a.dataset, a.config, a.split, a.limit, Path(a.out))
    elif a.cmd == "sweep":
        sweep(a.limit, Path(a.out), a.only)
    elif a.cmd == "report":
        report(Path(a.data), Path(a.out))
    elif a.cmd == "ingest-json":
        ingest_json([f for p in a.paths for f in glob.glob(p)], Path(a.out))


if __name__ == "__main__":
    main()
