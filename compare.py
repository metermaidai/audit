#!/usr/bin/env python3
"""
compare.py — baseline against candidate fixes, on the same tasks, with the combined result
as the authoritative number.

Each arm is a directory written by trajectory_audit.py (it reads tasks.jsonl). The baseline is the workflow as it was; each candidate is the workflow with
one fix applied; the combined arm is every fix applied together.

  python compare.py --baseline audit-before --candidate cache=audit-cache --candidate trim=audit-trim \\
                    --combined both=audit-both --out compare

Rules the report follows, because each one has been broken by a savings claim before:

  Like cohorts.        Arms are compared on the tasks present in every arm (paired by task id).
                       Coverage is printed. A cohort under --min-tasks is inconclusive.
  Every attempt.       Cost is the cost of all attempts at a task, restarts included.
  Unknown stays unknown. Success rate is over tasks with a known outcome; the unknown count is
                       printed next to it. No successes gives an undefined ratio, not zero.
  Quality is a gate.   A candidate whose success rate falls by more than --quality-tolerance
                       points is rejected however much it saves.
  Overhead is netted.  --overhead arm=dollars subtracts what the fix costs to run.
  No adding.           Individual fixes are never summed. The combined arm is the claim; the
                       naive sum is printed beside it only to show the gap.
  Uncertainty.         A paired bootstrap over tasks gives a 90% interval on the cost change.
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import schema  # noqa: E402

VERIFIED, INCONCLUSIVE, REJECTED = "verified", "inconclusive", "rejected"


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def load_arm(path: Path) -> dict[str, dict]:
    """tasks.jsonl -> {task_id: task row}. Accepts the audit output directory or the file."""
    f = path / "tasks.jsonl" if path.is_dir() else path
    if not f.exists():
        sys.exit(f"{path}: no tasks.jsonl (run trajectory_audit.py on this arm first)")
    tasks = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks[t["task_id"]] = t
    return tasks


def parse_arm_arg(v: str) -> tuple[str, Path]:
    if "=" not in v:
        sys.exit(f"--candidate/--combined take name=path, got {v!r}")
    name, p = v.split("=", 1)
    return name.strip(), Path(p)


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------
def metrics(tasks: list[dict]) -> dict:
    n = len(tasks)
    cost = sum(t["total_cost"] for t in tasks)
    succ = sum(1 for t in tasks if t["outcome"] == schema.SUCCESS)
    fail = sum(1 for t in tasks if t["outcome"] == schema.FAILURE)
    unk = n - succ - fail
    known = succ + fail
    attempts = sum(t["attempts_n"] for t in tasks)
    return {
        "tasks": n, "attempts": attempts, "restarted": sum(1 for t in tasks if t["attempts_n"] > 1),
        "total_cost": cost, "cost_per_task": (cost / n) if n else None,
        "success": succ, "failure": fail, "unknown": unk,
        "success_rate": (succ / known) if known else None,
        "cost_per_successful_task": (cost / succ) if succ else None,
    }


def bootstrap_delta(base: list[dict], cand: list[dict], n: int = 1000, seed: int = 7) -> dict | None:
    """Paired over tasks: resample task ids, recompute total cost change. 90% interval."""
    if len(base) < 2:
        return None
    rnd = random.Random(seed)
    pairs = list(zip(base, cand))
    deltas = []
    for _ in range(n):
        sample = [pairs[rnd.randrange(len(pairs))] for _ in pairs]
        b = sum(t["total_cost"] for t, _ in sample)
        c = sum(t["total_cost"] for _, t in sample)
        if b:
            deltas.append((c - b) / b)
    if not deltas:
        return None
    deltas.sort()
    return {"p05": deltas[int(0.05 * (len(deltas) - 1))], "p50": deltas[int(0.5 * (len(deltas) - 1))],
            "p95": deltas[int(0.95 * (len(deltas) - 1))], "resamples": n}


def judge(base: dict, cand: dict, overhead: float, tolerance_pp: float, min_tasks: int, ci: dict | None) -> tuple[str, list[str]]:
    reasons = []
    if cand["tasks"] < min_tasks:
        reasons.append(f"paired cohort has {cand['tasks']} tasks, under the {min_tasks} minimum")
        return INCONCLUSIVE, reasons
    gross = base["total_cost"] - cand["total_cost"]
    net = gross - overhead
    if base["success_rate"] is None or cand["success_rate"] is None:
        reasons.append("no outcome labels on one or both arms, so quality cannot be judged")
        status = INCONCLUSIVE
    else:
        drop_pp = (base["success_rate"] - cand["success_rate"]) * 100
        if drop_pp > tolerance_pp:
            reasons.append(f"success rate fell {drop_pp:.1f} points, beyond the {tolerance_pp:.1f}-point tolerance")
            return REJECTED, reasons
        reasons.append(f"success rate within tolerance ({drop_pp:+.1f} points)")
        status = VERIFIED
    if net <= 0:
        reasons.append(f"no net saving: gross {gross:+,.2f} minus overhead {overhead:,.2f} = {net:+,.2f}")
        return REJECTED, reasons
    if ci and ci["p95"] >= 0:
        reasons.append(f"the 90% interval on the cost change ({ci['p05']:+.0%} to {ci['p95']:+.0%}) includes zero")
        status = INCONCLUSIVE
    reasons.append(f"net saving {net:,.2f} on the paired cohort")
    return status, reasons


# ---------------------------------------------------------------------------
def compare(baseline: dict[str, dict], arms: dict[str, dict[str, dict]], combined_name: str | None,
            overhead: dict[str, float], tolerance_pp: float, min_tasks: int) -> dict:
    all_ids = set(baseline)
    for a in arms.values():
        all_ids &= set(a)
    paired = sorted(all_ids)
    coverage = {"baseline_tasks": len(baseline), "paired_tasks": len(paired),
                "paired_share_of_baseline": (len(paired) / len(baseline)) if baseline else None,
                "arms": {name: {"tasks": len(a), "not_in_baseline": len(set(a) - set(baseline))} for name, a in arms.items()}}
    base_rows = [baseline[i] for i in paired]
    base_m = metrics(base_rows)
    results = {}
    for name, a in arms.items():
        rows = [a[i] for i in paired]
        m = metrics(rows)
        ci = bootstrap_delta(base_rows, rows)
        oh = overhead.get(name, 0.0)
        status, reasons = judge(base_m, m, oh, tolerance_pp, min_tasks, ci)
        results[name] = {
            **m,
            "role": "combined" if name == combined_name else "candidate",
            "overhead": oh,
            "gross_saving": base_m["total_cost"] - m["total_cost"],
            "net_saving": base_m["total_cost"] - m["total_cost"] - oh,
            "cost_change": ((m["total_cost"] - base_m["total_cost"]) / base_m["total_cost"]) if base_m["total_cost"] else None,
            "cost_change_interval_90": ci,
            "success_rate_change_pp": ((m["success_rate"] - base_m["success_rate"]) * 100
                                       if m["success_rate"] is not None and base_m["success_rate"] is not None else None),
            "cost_per_successful_task_change": ((m["cost_per_successful_task"] - base_m["cost_per_successful_task"]) / base_m["cost_per_successful_task"]
                                               if m["cost_per_successful_task"] and base_m["cost_per_successful_task"] else None),
            "status": status, "reasons": reasons,
        }
    individual = [r for n, r in results.items() if r["role"] == "candidate"]
    naive_sum = sum(r["net_saving"] for r in individual) if len(individual) > 1 else None
    combined = results.get(combined_name) if combined_name else None
    if combined:
        headline = {"basis": "the combined arm, measured", "net_saving": combined["net_saving"], "status": combined["status"],
                    "naive_sum_of_individual_fixes": naive_sum,
                    "note": "The combined arm is the claim. The naive sum is shown only to make the overlap visible; it is never the claim."}
    elif len(individual) == 1:
        headline = {"basis": "the single candidate, measured", "net_saving": individual[0]["net_saving"], "status": individual[0]["status"],
                    "naive_sum_of_individual_fixes": None, "note": ""}
    else:
        headline = {"basis": "none: several candidates and no combined arm", "net_saving": None, "status": INCONCLUSIVE,
                    "naive_sum_of_individual_fixes": naive_sum,
                    "note": "Individual fixes cannot be added; run the combined configuration to get a combined number."}
    return {"schema_version": schema.SCHEMA_VERSION, "quality_tolerance_pp": tolerance_pp, "min_tasks": min_tasks,
            "coverage": coverage, "baseline": base_m, "arms": results, "headline": headline,
            "latency": "not in this data: trajectory records carry no timing"}


# ---------------------------------------------------------------------------
def fmt_money(v):
    return "—" if v is None else f"${v:,.2f}"


def fmt_pct(v):
    return "—" if v is None else f"{v:+.0%}" if isinstance(v, float) and abs(v) < 10 else f"{v}"


def render(res: dict) -> str:
    cov, b, h = res["coverage"], res["baseline"], res["headline"]
    L = ["# metermaid comparison\n",
         f"Baseline against {len(res['arms'])} arm(s) on the {cov['paired_tasks']:,} tasks present in every arm "
         f"({cov['paired_share_of_baseline']:.0%} of the baseline's {cov['baseline_tasks']:,}). "
         f"Cost counts every attempt at a task. Quality tolerance {res['quality_tolerance_pp']:.1f} points; "
         f"minimum cohort {res['min_tasks']} tasks. {res['latency'].capitalize()}.\n",
         "## Result\n"]
    if h["net_saving"] is not None:
        L.append(f"**{h['status'].upper()}** — net saving {fmt_money(h['net_saving'])} on the paired cohort ({h['basis']}).")
    else:
        L.append(f"**{h['status'].upper()}** — {h['basis']}.")
    if h["naive_sum_of_individual_fixes"] is not None:
        L.append(f"Naive sum of the individual fixes: {fmt_money(h['naive_sum_of_individual_fixes'])}. {h['note']}")
    elif h["note"]:
        L.append(h["note"])
    L.append("\n| arm | role | tasks | attempts | cost | Δ cost | 90% interval | success | Δ pp | unknown | $/success | overhead | net saving | status |")
    L.append("|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---|")
    sr = lambda m: "—" if m["success_rate"] is None else f"{m['success_rate']:.0%}"
    L.append(f"| baseline | baseline | {b['tasks']:,} | {b['attempts']:,} | {fmt_money(b['total_cost'])} | — | — | {sr(b)} | — | {b['unknown']:,} | {fmt_money(b['cost_per_successful_task'])} | — | — | — |")
    for name, r in res["arms"].items():
        ci = r["cost_change_interval_90"]
        ci_s = f"{ci['p05']:+.0%} to {ci['p95']:+.0%}" if ci else "—"
        dpp = "—" if r["success_rate_change_pp"] is None else f"{r['success_rate_change_pp']:+.1f}"
        L.append(f"| {name} | {r['role']} | {r['tasks']:,} | {r['attempts']:,} | {fmt_money(r['total_cost'])} | {fmt_pct(r['cost_change'])} | {ci_s} | "
                 f"{sr(r)} | {dpp} | {r['unknown']:,} | {fmt_money(r['cost_per_successful_task'])} | {fmt_money(r['overhead'])} | "
                 f"{fmt_money(r['net_saving'])} | {r['status']} |")
    for name, r in res["arms"].items():
        L.append(f"\n### {name}: {r['status']}\n")
        L += [f"- {reason}" for reason in r["reasons"]]
    L.append("\n## Coverage\n")
    for name, c in cov["arms"].items():
        L.append(f"- {name}: {c['tasks']:,} tasks, {c['not_in_baseline']:,} not in the baseline (excluded)")
    L.append("\nUnknown outcomes stay unknown and are excluded from the success rate, never counted as failures. "
             "A cost per successful task of — means no task succeeded or none carries an outcome.")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline", required=True, help="trajectory_audit.py output directory for the workflow as it was")
    ap.add_argument("--candidate", action="append", default=[], metavar="NAME=PATH", help="one fix applied; repeatable")
    ap.add_argument("--combined", default=None, metavar="NAME=PATH", help="every fix applied together")
    ap.add_argument("--overhead", action="append", default=[], metavar="NAME=DOLLARS", help="what the fix costs to run over the window")
    ap.add_argument("--quality-tolerance", type=float, default=2.0, help="max success-rate drop in percentage points (default 2)")
    ap.add_argument("--min-tasks", type=int, default=20, help="paired cohort smaller than this is inconclusive (default 20)")
    ap.add_argument("--out", default="./compare")
    a = ap.parse_args()
    if not a.candidate and not a.combined:
        sys.exit("give at least one --candidate or --combined")
    baseline = load_arm(Path(a.baseline))
    arms: dict[str, dict] = {}
    for v in a.candidate:
        name, p = parse_arm_arg(v)
        arms[name] = load_arm(p)
    combined_name = None
    if a.combined:
        combined_name, p = parse_arm_arg(a.combined)
        arms[combined_name] = load_arm(p)
    overhead = {}
    for v in a.overhead:
        name, d = v.split("=", 1)
        overhead[name.strip()] = float(d)
    res = compare(baseline, arms, combined_name, overhead, a.quality_tolerance, a.min_tasks)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "compare.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    md = render(res)
    (out / "compare.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\nWrote {out / 'compare.md'} and {out / 'compare.json'}")


if __name__ == "__main__":
    main()
