#!/usr/bin/env python3
"""
hf_pull.py — dump agent trajectories from a Hugging Face dataset into one JSON file
per run, in a folder trajectory_audit.py can read.

    python -m pip install datasets
    python hf_pull.py nebius/SWE-agent-trajectories --limit 2000 --out ./hf/nebius-sweagent
    python hf_pull.py <dataset> --inspect          # print columns + one row's shape, write nothing

Works on any dataset whose rows contain a trajectory-like field: "trajectory", "messages",
"history", "steps", or "traj" — as a list or as a JSON string. Rows are written as-is
(plus a normalized copy of the trajectory field) so the audit's parsers can auto-detect the format.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

try:
    from datasets import load_dataset
except ImportError:
    sys.exit("python -m pip install datasets")

TRAJ_KEYS = ("trajectory", "messages", "history", "steps", "traj")
ID_KEYS = ("instance_id", "id", "task_id", "problem_id")


def find_traj(row: dict):
    for k in TRAJ_KEYS:
        v = row.get(k)
        if v is None:
            continue
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                continue
        if isinstance(v, list) and v:
            return k, v
        if isinstance(v, dict):
            for kk in TRAJ_KEYS:
                if isinstance(v.get(kk), list):
                    return k, v[kk]
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("--config", default=None)
    ap.add_argument("--split", default="train")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--out", default="./hf")
    ap.add_argument("--inspect", action="store_true")
    a = ap.parse_args()

    ds = load_dataset(a.dataset, a.config, split=a.split, streaming=True)
    it = iter(ds)
    first = next(it)
    print("columns:", list(first.keys()), file=sys.stderr)
    k, traj = find_traj(first)
    if k:
        print(f"trajectory field: '{k}', {len(traj)} items, first item: "
              f"{list(traj[0].keys()) if isinstance(traj[0], dict) else str(traj[0])[:200]}", file=sys.stderr)
    if a.inspect or not k:
        print(json.dumps({kk: (str(vv)[:300] if not isinstance(vv, (int, float, bool)) else vv) for kk, vv in first.items()}, indent=1)[:4000])
        if not k:
            sys.exit("no trajectory-like field found; paste this output to get a parser added")
        print(f"\ntrajectory field: '{k}', {len(traj)} items, first item keys: "
              f"{list(traj[0].keys()) if isinstance(traj[0], dict) else type(traj[0]).__name__}")
        if a.inspect:
            return

    out = Path(a.out) / a.dataset.replace("/", "__")
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for row in [first] + list(it) if a.limit <= 1 else _take([first], it, a.limit):
        k, traj = find_traj(row)
        if not k:
            continue
        rid = next((str(row[i]) for i in ID_KEYS if row.get(i)), "row")
        model = str(row.get("model_name") or row.get("model") or "").replace("/", "_")[:40]
        rid = f"{rid}__{model}__{n:05d}" if model else f"{rid}__{n:05d}"
        doc = {kk: vv for kk, vv in row.items() if kk != k}
        doc[k] = traj
        # surface cost/tokens if the dataset carries them under common names
        info = doc.setdefault("info", {}) if isinstance(doc.get("info"), (dict, type(None))) else {}
        ms = {}
        for src, dst in (("cost", "instance_cost"), ("total_cost", "instance_cost"), ("instance_cost", "instance_cost"),
                         ("tokens_sent", "tokens_sent"), ("input_tokens", "tokens_sent"), ("prompt_tokens", "tokens_sent"),
                         ("tokens_received", "tokens_received"), ("output_tokens", "tokens_received"), ("completion_tokens", "tokens_received"),
                         ("api_calls", "api_calls")):
            if isinstance(row.get(src), (int, float)):
                ms[dst] = row[src]
        if ms and isinstance(info, dict):
            info.setdefault("model_stats", ms)
        if isinstance(info, dict) and row.get("exit_status"):
            info.setdefault("exit_status", row["exit_status"])
        if isinstance(info, dict) and info:
            doc["info"] = info
        (out / f"{rid.replace('/', '__')}.json").write_text(json.dumps(doc, default=str), encoding="utf-8")
        n += 1
        if n % 200 == 0:
            print(f"  {n} written", file=sys.stderr)
    print(f"wrote {n} trajectories to {out}", file=sys.stderr)


def _take(head, it, limit):
    yield from head
    for i, row in enumerate(it, start=len(head)):
        if i >= limit:
            return
        yield row


if __name__ == "__main__":
    main()
