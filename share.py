#!/usr/bin/env python3
"""
share.py — the one payload from an audit that is meant to leave the machine.

The local reports (audit/audit.json, traj-audit/trajectory-audit.json) are written for the
operator and carry things that should stay local: run ids that are often repo and issue names,
the worst runs' commands, file paths, owner emails, per-key spend with the operator's own labels.
`--share` on either auditor writes a second file, share.json, built by allowlist from the local
result: only the fields named here are copied, and every identifier that survives is replaced
by a salted pseudonym. Nothing else in the local report is ever read for it.

The salt matters for repeat audits. With --salt fixed, the same submission or key hashes to the
same pseudonym next month, so two share files can be compared; without it the salt is random
and the pseudonyms are one-off. Keep the salt like a password: it never goes in the payload.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

# What a share payload never carries, stated inside the payload so a reader does not have
# to trust the README. Tests check these against the actual output.
OMITTED = [
    "per-run rows",
    "run, trajectory and instance ids",
    "commands, prompts and tool output, including the worst-run notes",
    "file paths and unparsed-file lists",
    "owner emails and team names",
    "raw key, workspace and project ids",
]


def new_salt() -> str:
    return secrets.token_hex(8)


def pseudonym(value: str, salt: str, prefix: str = "") -> str:
    """Stable for a given (value, salt); unrelatable to the value without the salt."""
    h = hashlib.sha256(f"{salt}\x00{value}".encode("utf-8")).hexdigest()[:10]
    return f"{prefix}{h}" if prefix else h


def _num(v):
    return v if isinstance(v, (int, float)) or v is None else None


def _curve(rows) -> list[dict]:
    """The five aggregate quintile rows and nothing else."""
    out = []
    for c in rows or []:
        out.append({k: _num(c.get(k)) for k in
                    ("q", "n", "steps_lo", "steps_hi", "cost", "cost_share", "resolve", "resolved_per_dollar")})
    return out


# ---------------------------------------------------------------------------
# trajectory audit
# ---------------------------------------------------------------------------
def trajectory_share(res: dict, salt: str) -> dict:
    subs = {}
    for label, s in (res.get("submissions") or {}).items():
        by_det = {}
        for det, v in (s.get("by_detector") or {}).items():
            by_det[det] = {"trajs": _num(v.get("trajs")), "share_of_trajs": _num(v.get("share_of_trajs")),
                           "cost": _num(v.get("cost"))}
        # the worst runs, stripped to detector and size: no id, no note, no command
        worst = [{"detector": h.get("detector"), "wasted_steps": _num(h.get("wasted_steps")),
                  "wasted_cost": _num(h.get("wasted_cost"))} for h in (s.get("worst") or [])]
        subs[pseudonym(label, salt, "sub_")] = {
            "trajectories": _num(s.get("trajectories")),
            "cost_source": s.get("cost_source"),
            "total_cost": _num(s.get("total_cost")),
            "mean_cost": _num(s.get("mean_cost")),
            "median_cost": _num(s.get("median_cost")),
            "mean_steps": _num(s.get("mean_steps")),
            "p90_steps": _num(s.get("p90_steps")),
            "runs_over_2x_p90_steps": _num(s.get("runs_over_2x_p90_steps")),
            "trajs_with_any_finding": _num(s.get("trajs_with_any_finding")),
            "waste_cost": _num(s.get("waste_cost")), "waste_share": _num(s.get("waste_share")),
            "sunk_cost": _num(s.get("sunk_cost")), "sunk_share": _num(s.get("sunk_share")),
            "resolve_rate": _num(s.get("resolve_rate")),
            "resolve_rate_with_findings": _num(s.get("resolve_rate_with_findings")),
            "resolve_rate_without_findings": _num(s.get("resolve_rate_without_findings")),
            "by_detector": by_det,
            "worst": worst,
            "curve": _curve(s.get("curve")),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "trajectory_audit",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "omitted": list(OMITTED),
        "trajectories": _num(res.get("trajectories")),
        "total_cost": _num(res.get("total_cost")),
        "waste_cost": _num(res.get("waste_cost")), "waste_share": _num(res.get("waste_share")),
        "sunk_cost": _num(res.get("sunk_cost")), "sunk_share": _num(res.get("sunk_share")),
        "curve": _curve(res.get("curve")),
        "tasks": {k: (v if k in ("id_sources", "cost_per_successful_task_basis") else _num(v))
                  for k, v in (res.get("tasks") or {}).items()},
        "submissions": subs,
    }


# ---------------------------------------------------------------------------
# spend audit
# ---------------------------------------------------------------------------
def spend_share(res: dict, invoiced: dict, salt: str) -> dict:
    findings = []
    for f in res.get("findings") or []:
        findings.append({
            "id": f.get("id"), "title": f.get("title"),
            "scope": "org" if f.get("scope") == "org" else pseudonym(str(f.get("scope")), salt, "agent_"),
            "monthly_waste": _num(f.get("monthly_waste")),
            "evidence_level": f.get("evidence_level"), "assumption": f.get("assumption"),
            "evidence": f.get("evidence"), "fix": f.get("fix"),
        })
    keys = []
    for k in res.get("top_keys_monthly") or []:
        keys.append({
            "key": pseudonym(str(k.get("key")), salt, "key_"),
            "monthly_cost": _num(k.get("monthly_cost")),
            "requests_monthly": _num(k.get("requests_monthly")),
            "tokens_monthly": _num(k.get("tokens_monthly")),
            "frontier_share": _num(k.get("frontier_share")),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": "metermaid_audit",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "omitted": list(OMITTED),
        "window_days": _num(res.get("window_days")),
        "price_version": res.get("price_version"),
        "estimated_spend_monthly": _num(res.get("estimated_spend_monthly")),
        "provider_reported_cost_window": {p: _num(v) for p, v in (invoiced or {}).items()},
        "by_provider_monthly": {p: _num(v) for p, v in (res.get("by_provider_monthly") or {}).items()},
        "by_model_monthly": {m: _num(v) for m, v in (res.get("by_model_monthly") or {}).items()},
        "unowned_share": _num(res.get("unowned_share")),
        "frontier_share_of_spend": _num(res.get("frontier_share_of_spend")),
        "opportunity": {k: _num(v) if k != "basis" else v for k, v in (res.get("opportunity") or {}).items()},
        "findings": findings,
        "top_keys_monthly": keys,
        "unknown_models": list(res.get("unknown_models") or []),
        "stale_prices": [{"model": s.get("model"), "verified_on": s.get("verified_on")}
                         for s in (res.get("stale_prices") or [])],
    }


# ---------------------------------------------------------------------------
def preview(payload: dict) -> str:
    """What is in the file and what is not, printed before anything is sent anywhere."""
    lines = [f"share.json (schema v{payload['schema_version']}, {payload['tool']}) contains:"]
    for k, v in payload.items():
        if k in ("schema_version", "tool", "omitted"):
            continue
        if isinstance(v, dict):
            lines.append(f"  {k}: {len(v)} entr{'y' if len(v) == 1 else 'ies'}")
        elif isinstance(v, list):
            lines.append(f"  {k}: {len(v)} row{'' if len(v) == 1 else 's'}")
        else:
            lines.append(f"  {k}: {v}")
    lines.append("and never contains:")
    lines += [f"  - {o}" for o in payload["omitted"]]
    return "\n".join(lines)


def write_share(payload: dict, out: Path, name: str = "share.json") -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
