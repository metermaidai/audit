#!/usr/bin/env python3
"""
metermaid audit — Phase 0

Pulls 30 days of usage and cost from the Anthropic and OpenAI admin APIs,
prices it, and writes a one-page audit: spend, unowned share, over-tier share,
estimated monthly waste, and the top fixes.

Runs entirely on the operator's machine. Keys never leave it.

    python metermaid_audit.py --days 30 --out ./audit
    ANTHROPIC_ADMIN_KEY=sk-ant-admin-...  OPENAI_ADMIN_KEY=sk-admin-...
    python metermaid_audit.py --demo      # synthetic data, no keys needed

Requires: python 3.10+, requests
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

HERE = Path(__file__).resolve().parent
ANTHROPIC_BASE = "https://api.anthropic.com"
OPENAI_BASE = "https://api.openai.com"


# ---------------------------------------------------------------------------
# Normalized usage row
# ---------------------------------------------------------------------------
@dataclass
class Row:
    provider: str            # anthropic | openai
    key_id: str              # api key id (or project id when key absent)
    scope_id: str            # workspace_id / project_id
    model: str
    bucket_start: datetime   # UTC
    bucket_hours: float
    requests: int
    tokens_in: int           # uncached input
    cache_read: int
    cache_write: int
    tokens_out: int
    batch: bool = False
    est_cost: float = 0.0
    tier: str = "unknown"


# ---------------------------------------------------------------------------
# Rate card
# ---------------------------------------------------------------------------
class RateCard:
    def __init__(self, path: Path):
        self.cfg = json.loads(path.read_text())
        self.models = self.cfg["models"]
        self.prefixes = sorted(self.models.keys(), key=len, reverse=True)
        self.unknown: set[str] = set()

    def lookup(self, model: str) -> dict | None:
        m = model.lower()
        for p in self.prefixes:
            if m.startswith(p):
                return self.models[p]
        self.unknown.add(model)
        return None

    def price(self, r: Row) -> tuple[float, str]:
        spec = self.lookup(r.model)
        if not spec:
            # unknown model: tier by name heuristics, priced at tier reference
            tier = "small" if any(x in r.model for x in ("mini", "nano", "haiku", "small")) else \
                   "frontier" if any(x in r.model for x in ("opus", "o3", "gpt-5", "pro")) else "mid"
            ref = self.cfg["tier_reference_price"][tier]
            spec = {"tier": tier, "input": ref["input"], "output": ref["output"],
                    "cache_read": ref["input"] * 0.1, "cache_write": ref["input"] * 1.25}
        mult = self.cfg["batch_discount"] if r.batch else 1.0
        cost = (r.tokens_in * spec["input"] + r.cache_read * spec["cache_read"] +
                r.cache_write * spec["cache_write"] + r.tokens_out * spec["output"]) / 1e6 * mult
        return cost, spec["tier"]

    def tier_ref(self, tier: str) -> dict:
        return self.cfg["tier_reference_price"][tier]

    def substitute(self, tier: str) -> str | None:
        return self.cfg["tier_substitute"].get(tier)


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------
def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get(url, headers, params, retries=5):
    for attempt in range(retries):
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(min(2 ** attempt, 20))
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"{url} -> {resp.status_code}: {resp.text[:400]}")
        return resp.json()
    raise RuntimeError(f"{url}: gave up after {retries} retries")


def fetch_anthropic(admin_key: str, start: datetime, end: datetime) -> tuple[list[Row], float]:
    """Usage report (hourly) + cost report (daily) from the Anthropic Admin API."""
    headers = {"x-api-key": admin_key, "anthropic-version": "2023-06-01"}
    rows: list[Row] = []
    params = {
        "starting_at": _iso(start), "ending_at": _iso(end), "bucket_width": "1h",
        "group_by[]": ["api_key_id", "workspace_id", "model", "service_tier"], "limit": 168,
    }
    page = None
    while True:
        p = dict(params)
        if page:
            p["page"] = page
        data = _get(f"{ANTHROPIC_BASE}/v1/organizations/usage_report/messages", headers, p)
        for bucket in data.get("data", []):
            bs = datetime.fromisoformat(bucket["starting_at"].replace("Z", "+00:00"))
            for res in bucket.get("results", []):
                cc = res.get("cache_creation") or {}
                cache_write = int(cc.get("ephemeral_5m_input_tokens", 0) or 0) + int(cc.get("ephemeral_1h_input_tokens", 0) or 0)
                rows.append(Row(
                    provider="anthropic",
                    key_id=res.get("api_key_id") or "unknown-key",
                    scope_id=res.get("workspace_id") or "default",
                    model=res.get("model") or "unknown",
                    bucket_start=bs, bucket_hours=1.0,
                    requests=int(res.get("request_count") or res.get("requests") or 0),
                    tokens_in=int(res.get("uncached_input_tokens") or 0),
                    cache_read=int(res.get("cache_read_input_tokens") or 0),
                    cache_write=cache_write,
                    tokens_out=int(res.get("output_tokens") or 0),
                    batch=(res.get("service_tier") == "batch"),
                ))
        if data.get("has_more") and data.get("next_page"):
            page = data["next_page"]
        else:
            break

    invoiced = 0.0
    p = {"starting_at": _iso(start.replace(hour=0, minute=0, second=0)), "ending_at": _iso(end),
         "bucket_width": "1d", "group_by[]": ["workspace_id"], "limit": 31}
    page = None
    while True:
        if page:
            p["page"] = page
        data = _get(f"{ANTHROPIC_BASE}/v1/organizations/cost_report", headers, p)
        for bucket in data.get("data", []):
            for res in bucket.get("results", []):
                amt = res.get("amount")
                # amounts are strings in lowest currency unit (cents) in USD
                try:
                    invoiced += float(amt) / 100.0
                except (TypeError, ValueError):
                    pass
        if data.get("has_more") and data.get("next_page"):
            page = data["next_page"]
        else:
            break
    return rows, invoiced


def fetch_openai(admin_key: str, start: datetime, end: datetime) -> tuple[list[Row], float]:
    """Completions usage (hourly) + costs (daily) from the OpenAI Admin API."""
    headers = {"Authorization": f"Bearer {admin_key}"}
    rows: list[Row] = []
    params = {
        "start_time": int(start.timestamp()), "end_time": int(end.timestamp()),
        "bucket_width": "1h", "group_by": ["model", "project_id", "api_key_id", "batch"], "limit": 168,
    }
    page = None
    while True:
        p = dict(params)
        if page:
            p["page"] = page
        data = _get(f"{OPENAI_BASE}/v1/organization/usage/completions", headers, p)
        for bucket in data.get("data", []):
            bs = datetime.fromtimestamp(bucket["start_time"], tz=timezone.utc)
            for res in bucket.get("results", []):
                cached = int(res.get("input_cached_tokens") or 0)
                rows.append(Row(
                    provider="openai",
                    key_id=res.get("api_key_id") or res.get("project_id") or "unknown-key",
                    scope_id=res.get("project_id") or "default",
                    model=res.get("model") or "unknown",
                    bucket_start=bs, bucket_hours=1.0,
                    requests=int(res.get("num_model_requests") or 0),
                    tokens_in=max(int(res.get("input_tokens") or 0) - cached, 0),
                    cache_read=cached, cache_write=0,
                    tokens_out=int(res.get("output_tokens") or 0),
                    batch=bool(res.get("batch")),
                ))
        if data.get("has_more") and data.get("next_page"):
            page = data["next_page"]
        else:
            break

    invoiced = 0.0
    p = {"start_time": int(start.timestamp()), "end_time": int(end.timestamp()),
         "bucket_width": "1d", "group_by": ["project_id"], "limit": 31}
    page = None
    while True:
        if page:
            p["page"] = page
        data = _get(f"{OPENAI_BASE}/v1/organization/costs", headers, p)
        for bucket in data.get("data", []):
            for res in bucket.get("results", []):
                amt = (res.get("amount") or {}).get("value")
                try:
                    invoiced += float(amt)
                except (TypeError, ValueError):
                    pass
        if data.get("has_more") and data.get("next_page"):
            page = data["next_page"]
        else:
            break
    return rows, invoiced


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------
def demo_rows(start: datetime, days: int) -> tuple[list[Row], dict[str, float]]:
    random.seed(7)
    keys = [
        # key, provider, scope, model, req/hr, in, out, cache_share, pattern
        ("apikey_support", "anthropic", "ws_cx", "claude-opus-4-1", 400, 1800, 120, 0.05, "flat"),        # over-tier + no cache
        ("apikey_pr", "anthropic", "ws_eng", "claude-sonnet-4-5", 60, 9000, 900, 0.55, "growth"),         # context growth
        ("apikey_nightly", "anthropic", "ws_data", "claude-sonnet-4-5", 0, 4000, 600, 0.0, "nightly"),    # batch-eligible
        ("key_research", "openai", "proj_prod", "gpt-5", 30, 6000, 1500, 0.3, "flat"),
        ("key_classify", "openai", "proj_prod", "gpt-5", 900, 400, 40, 0.0, "flat"),                     # over-tier
        ("key_orphan", "openai", "proj_old", "gpt-4o", 15, 2000, 300, 0.1, "spike"),                       # velocity spike
    ]
    rows = []
    for d in range(days):
        for h in range(24):
            ts = start + timedelta(days=d, hours=h)
            for key, prov, scope, model, rph, tin, tout, cshare, pat in keys:
                r = rph
                if pat == "nightly":
                    r = 2500 if h in (2, 3) else 0
                elif pat == "growth":
                    tin = int(tin * (1 + 0.6 * d / days))
                elif pat == "spike" and d == days - 5:
                    r = rph * 12
                if pat != "nightly":
                    r = int(r * (0.6 + 0.8 * random.random()) * (0.4 if (ts.weekday() >= 5) else 1.0))
                if r <= 0:
                    continue
                total_in = r * tin
                rows.append(Row(prov, key, scope, model, ts, 1.0, r,
                                int(total_in * (1 - cshare)), int(total_in * cshare), 0, r * tout, False))
    return rows, {"anthropic": 0.0, "openai": 0.0}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
@dataclass
class Finding:
    id: str
    title: str
    scope: str
    monthly_waste: float
    confidence: float
    evidence: str
    fix: str


def key_label(r: Row, keymap: dict) -> tuple[str, str]:
    prov = keymap.get(r.provider, {})
    for ident in (r.key_id, r.scope_id):
        if ident in prov:
            e = prov[ident]
            return e.get("agent", ident), e.get("owner", "")
    return f"{r.provider}:{r.key_id}", ""


def analyze(rows: list[Row], rc: RateCard, keymap: dict, days: int) -> dict:
    scale = 30.0 / max(days, 1)
    for r in rows:
        r.est_cost, r.tier = rc.price(r)

    total = sum(r.est_cost for r in rows)
    by_provider = defaultdict(float)
    by_model = defaultdict(float)
    by_key = defaultdict(lambda: {"cost": 0.0, "requests": 0, "tokens_in": 0, "cache_read": 0,
                                  "cache_write": 0, "tokens_out": 0, "frontier_cost": 0.0,
                                  "frontier_tokens": 0, "tokens": 0, "provider": "", "batch_req": 0,
                                  "hours": defaultdict(int), "rows": []})
    for r in rows:
        by_provider[r.provider] += r.est_cost
        by_model[r.model] += r.est_cost
        k = by_key[(r.provider, r.key_id)]
        k["provider"] = r.provider
        k["cost"] += r.est_cost
        k["requests"] += r.requests
        k["tokens_in"] += r.tokens_in
        k["cache_read"] += r.cache_read
        k["cache_write"] += r.cache_write
        k["tokens_out"] += r.tokens_out
        tk = r.tokens_in + r.cache_read + r.cache_write + r.tokens_out
        k["tokens"] += tk
        if r.tier == "frontier":
            k["frontier_cost"] += r.est_cost
            k["frontier_tokens"] += tk
        if r.batch:
            k["batch_req"] += r.requests
        k["hours"][r.bucket_start.hour] += r.requests
        k["rows"].append(r)

    findings: list[Finding] = []

    # L02 unowned spend
    unowned = 0.0
    for (prov, kid), k in by_key.items():
        label, owner = key_label(k["rows"][0], keymap)
        if not owner:
            unowned += k["cost"]
    if total and unowned / total > 0.05:
        findings.append(Finding("L02", "Spend with no named owner", "org", 0.0, 1.0,
                                f"${unowned * scale:,.0f}/mo ({unowned / total:.0%} of spend) is on keys/projects not in keymap.json",
                                "Assign an owner to every key; rotate keys nobody claims within 14 days"))

    for (prov, kid), k in by_key.items():
        r0 = k["rows"][0]
        label, owner = key_label(r0, keymap)
        month_cost = k["cost"] * scale
        if k["requests"] == 0:
            continue
        avg_out = k["tokens_out"] / k["requests"]
        frontier_share = k["frontier_tokens"] / k["tokens"] if k["tokens"] else 0

        # L01 over-tier mix
        if frontier_share > 0.6 and avg_out < 300 and k["requests"] * scale > 10_000:
            # reprice frontier traffic at mid-tier reference
            mid = rc.tier_ref("mid")
            fr_rows = [r for r in k["rows"] if r.tier == "frontier"]
            mid_cost = sum((r.tokens_in + r.cache_read * 0.1 + r.cache_write * 1.25) * mid["input"]
                           + r.tokens_out * mid["output"] for r in fr_rows) / 1e6
            delta = (k["frontier_cost"] - mid_cost) * 0.5 * scale
            if delta > 100:
                findings.append(Finding("L01", "Frontier model on short, high-volume traffic", label, delta, 0.6,
                                        f"{frontier_share:.0%} of tokens on frontier tier; avg output {avg_out:.0f} tokens; "
                                        f"{k['requests'] * scale:,.0f} req/mo; ${k['frontier_cost'] * scale:,.0f}/mo on frontier",
                                        "Route this task shape to a mid-tier model; validate on a 200-task shadow replay before switching"))

        # L05 cache under-use (priced at mid-tier if L01 already fired, to avoid double counting)
        in_total = k["tokens_in"] + k["cache_read"] + k["cache_write"]
        if k["requests"] * scale > 1_000 and in_total:
            cache_share = k["cache_read"] / in_total
            if cache_share < 0.2:
                spec = rc.lookup(r0.model) or {"input": rc.tier_ref(r0.tier)["input"]}
                inp = spec["input"]
                if any(f.id == "L01" and f.scope == label for f in findings):
                    inp = rc.tier_ref("mid")["input"]
                saving = k["tokens_in"] * 0.5 * (inp - inp * 0.1) / 1e6 * scale
                if saving > 100:
                    findings.append(Finding("L05", "Prompt caching unused or ineffective", label, saving, 0.5,
                                            f"cache reads are {cache_share:.0%} of input tokens across {k['requests'] * scale:,.0f} req/mo; "
                                            f"{k['tokens_in'] * scale / 1e6:,.1f}M uncached input tokens/mo",
                                            "Move the stable system prompt and tool definitions to a cached prefix; assumes ~50% of input is repeated prefix"))

        # L06 token growth (first vs last 7 days)
        first = [r for r in k["rows"] if r.bucket_start < r0.bucket_start + timedelta(days=7)]
        last = [r for r in k["rows"] if r.bucket_start >= max(r.bucket_start for r in k["rows"]) - timedelta(days=7)]
        fr, lr = sum(r.requests for r in first), sum(r.requests for r in last)
        if fr > 200 and lr > 200:
            f_tpr = sum(r.tokens_in + r.cache_read for r in first) / fr
            l_tpr = sum(r.tokens_in + r.cache_read for r in last) / lr
            if l_tpr > f_tpr * 1.25 and 0.8 <= lr / fr <= 1.25:
                spec = rc.lookup(r0.model) or {"input": rc.tier_ref(r0.tier)["input"]}
                excess = (l_tpr - f_tpr) * lr * (30 / 7) * spec["input"] / 1e6
                if excess > 100:
                    findings.append(Finding("L06", "Input tokens per request growing", label, excess, 0.6,
                                            f"{f_tpr:,.0f} → {l_tpr:,.0f} input tokens/request over the window with flat request volume",
                                            "Trim accumulated context; truncate or summarize tool output; check for history not being compacted"))

        # L07 velocity anomaly (daily spend)
        daily = defaultdict(float)
        for r in k["rows"]:
            daily[r.bucket_start.date()] += r.est_cost
        vals = list(daily.values())
        if len(vals) >= 10:
            mu, sd = statistics.mean(vals), statistics.pstdev(vals)
            spikes = [(d, v) for d, v in daily.items() if sd > 0 and v > mu + 3 * sd and v - mu > 50]
            if spikes:
                excess = sum(v - mu for _, v in spikes)
                findings.append(Finding("L07", "Spend spike outside normal range", label, excess * scale, 0.7,
                                        f"{len(spikes)} day(s) above mean+3σ; largest ${max(v for _, v in spikes):,.0f} vs typical ${mu:,.0f}/day",
                                        "Set a daily budget alert on this key; add a rate limit or circuit breaker at the gateway"))

        # L10 batch-eligible
        hours = k["hours"]
        if k["requests"] * scale > 5_000 and k["batch_req"] / k["requests"] < 0.2:
            best = 0
            for h in range(24):
                best = max(best, hours[h] + hours[(h + 1) % 24])
            if best / k["requests"] > 0.8:
                saving = month_cost * (1 - k["batch_req"] / k["requests"]) * 0.5
                if saving > 100:
                    findings.append(Finding("L10", "Nightly/bursty workload not on batch pricing", label, saving, 0.7,
                                            f"{best / k['requests']:.0%} of requests land in a 2-hour daily window; batch share {k['batch_req'] / k['requests']:.0%}",
                                            "Move to the Batch API (50% discount) if 24h turnaround is acceptable"))

    findings.sort(key=lambda f: f.monthly_waste, reverse=True)
    waste = sum(f.monthly_waste for f in findings)
    top_keys = sorted(by_key.items(), key=lambda kv: kv[1]["cost"], reverse=True)[:10]

    return {
        "window_days": days,
        "estimated_spend_window": total,
        "estimated_spend_monthly": total * scale,
        "by_provider_monthly": {p: c * scale for p, c in by_provider.items()},
        "by_model_monthly": dict(sorted(((m, c * scale) for m, c in by_model.items()), key=lambda x: -x[1])),
        "top_keys_monthly": [
            {"key": f"{p}:{kid}", "label": key_label(k["rows"][0], keymap)[0], "owner": key_label(k["rows"][0], keymap)[1],
             "monthly_cost": k["cost"] * scale, "requests_monthly": k["requests"] * scale,
             "frontier_share": (k["frontier_tokens"] / k["tokens"]) if k["tokens"] else 0}
            for (p, kid), k in top_keys],
        "unowned_monthly": unowned * scale,
        "unowned_share": (unowned / total) if total else 0,
        "frontier_share_of_spend": (sum(r.est_cost for r in rows if r.tier == "frontier") / total) if total else 0,
        "estimated_monthly_waste": waste,
        "waste_share": (waste / (total * scale)) if total else 0,
        "findings": [asdict(f) for f in findings],
        "unknown_models": sorted(rc.unknown),
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def write_report(res: dict, invoiced: dict[str, float], out: Path):
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps({"result": res, "invoiced": invoiced}, indent=2, default=str))
    m = res
    lines = []
    lines.append("# metermaid audit\n")
    lines.append(f"Window: last {m['window_days']} days, normalized to 30. Estimated from provider usage APIs and a local rate card; reconcile against invoices.\n")
    lines.append("## The number\n")
    lines.append(f"- Estimated spend: **${m['estimated_spend_monthly']:,.0f}/month**")
    inv_total = sum(invoiced.values())
    if inv_total:
        lines.append(f"- Provider-reported cost for the window: ${inv_total:,.0f} (estimate for window: ${m['estimated_spend_window']:,.0f})")
    lines.append(f"- Estimated waste: **${m['estimated_monthly_waste']:,.0f}/month ({m['waste_share']:.0%} of spend)**")
    lines.append(f"- Spend with no named owner: ${m['unowned_monthly']:,.0f}/month ({m['unowned_share']:.0%})")
    lines.append(f"- Share of spend on frontier-tier models: {m['frontier_share_of_spend']:.0%}\n")
    lines.append("## Spend by provider\n")
    for p, c in m["by_provider_monthly"].items():
        lines.append(f"- {p}: ${c:,.0f}/month")
    lines.append("\n## Spend by model\n")
    for mdl, c in list(m["by_model_monthly"].items())[:12]:
        lines.append(f"- {mdl}: ${c:,.0f}/month")
    lines.append("\n## Top keys / agents\n")
    lines.append("| agent / key | owner | $/month | req/month | frontier share |")
    lines.append("|---|---|---:|---:|---:|")
    for k in m["top_keys_monthly"]:
        lines.append(f"| {k['label']} | {k['owner'] or '—'} | ${k['monthly_cost']:,.0f} | {k['requests_monthly']:,.0f} | {k['frontier_share']:.0%} |")
    lines.append("\n## Findings, ranked by dollars\n")
    if not m["findings"]:
        lines.append("No findings above threshold. Either this is a clean estate or the window is too short.")
    for i, f in enumerate(m["findings"], 1):
        amt = f"${f['monthly_waste']:,.0f}/month" if f["monthly_waste"] else "governance"
        lines.append(f"### {i}. {f['title']} — {amt}")
        lines.append(f"- Scope: {f['scope']}  ·  Detector {f['id']}  ·  Confidence {f['confidence']:.0%}")
        lines.append(f"- Evidence: {f['evidence']}")
        lines.append(f"- Fix: {f['fix']}\n")
    if m["unknown_models"]:
        lines.append("## Models priced at tier reference (add to ratecard.json)\n")
        for u in m["unknown_models"]:
            lines.append(f"- {u}")
    lines.append("\n---\nGenerated locally by metermaid audit (Phase 0). Keys were not transmitted anywhere.")
    (out / "audit.md").write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nWrote {out / 'audit.md'} and {out / 'audit.json'}")


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="metermaid audit — Phase 0")
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--out", default="./audit")
    ap.add_argument("--ratecard", default=str(HERE / "ratecard.json"))
    ap.add_argument("--keymap", default=str(HERE / "keymap.json"))
    ap.add_argument("--demo", action="store_true", help="synthetic data; no API keys needed")
    args = ap.parse_args()

    rc = RateCard(Path(args.ratecard))
    keymap = json.loads(Path(args.keymap).read_text()) if Path(args.keymap).exists() else {}
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=args.days)

    rows: list[Row] = []
    invoiced: dict[str, float] = {}
    if args.demo:
        rows, invoiced = demo_rows(start, args.days)
        keymap = {"anthropic": {"apikey_support": {"agent": "support-triage", "owner": "jane@demo"},
                                "apikey_pr": {"agent": "pr-reviewer", "owner": "dev@demo"}},
                  "openai": {"key_research": {"agent": "research-agent", "owner": "pm@demo"}}}
    else:
        akey = os.environ.get("ANTHROPIC_ADMIN_KEY")
        okey = os.environ.get("OPENAI_ADMIN_KEY")
        if not (akey or okey):
            sys.exit("Set ANTHROPIC_ADMIN_KEY and/or OPENAI_ADMIN_KEY, or run with --demo")
        if akey:
            print("Pulling Anthropic usage and cost…", file=sys.stderr)
            r, inv = fetch_anthropic(akey, start, end)
            rows += r
            invoiced["anthropic"] = inv
        if okey:
            print("Pulling OpenAI usage and costs…", file=sys.stderr)
            r, inv = fetch_openai(okey, start, end)
            rows += r
            invoiced["openai"] = inv
    if not rows:
        sys.exit("No usage rows returned for the window.")
    res = analyze(rows, rc, keymap, args.days)
    write_report(res, invoiced, Path(args.out))


if __name__ == "__main__":
    main()
