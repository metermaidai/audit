#!/usr/bin/env python3
"""
metermaid benchmark — turn one trajectory audit into a report, positioned against the Index.

Reads the JSON written by trajectory_audit.py and the checked-in Index (report/index.json),
and writes a single self-contained HTML page: where the spend sits by run length, the split
between productive spend and the three kinds of waste, and how each number compares with the
341,054 public runs in the Index.

Usage:
  python trajectory_audit.py ./your-traces --out ./traj-audit
  python benchmark.py traj-audit/trajectory-audit.json --org "Acme" --out benchmark.html

Everything runs locally. The input carries only the aggregates trajectory_audit.py computes;
no per-run rows are read, written, or sent anywhere.
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import date
from html import escape
from pathlib import Path

INK, YELLOW, PAPER, PANEL, MUTE, RULE, RED = "#141B2D", "#FFC72C", "#FFFFFF", "#F4F4EF", "#6E7484", "#DDDFE3", "#D8321F"


# ---------------------------------------------------------------------------
# Index comparison
# ---------------------------------------------------------------------------
def index_distributions(index: dict) -> dict[str, list[float]]:
    """The per-group values the Index reports, one list per metric we benchmark against."""
    groups = index.get("groups", [])
    q5 = [m["cost_share"] for m in index.get("marginal", []) if m.get("q") == 5 and m.get("cost_share") is not None]
    return {
        "tail_share": q5,
        "waste_share": [g["mech_share"] for g in groups if g.get("mech_share") is not None],
        "sunk_share": [g["sunk_share"] for g in groups if g.get("sunk_share") is not None],
        "bloat_rate": [g["bloat_rate"] for g in groups if g.get("bloat_rate") is not None],
    }


def rank(value: float | None, population: list[float]) -> dict | None:
    """Where a value falls in the Index's spread. Returns counts, never a bare percentile."""
    if value is None or not population:
        return None
    below = sum(1 for p in population if p < value)
    return {
        "below": below,
        "total": len(population),
        "median": statistics.median(population),
        "worse_than_median": value > statistics.median(population),
    }


def phrase(r: dict | None, higher_is_worse: bool = True) -> str:
    """Say where the value sits by counting groups, not by quoting a percentile."""
    if not r:
        return "no comparable Index groups"
    if r["worse_than_median"]:
        side = f"higher than {r['below']} of {r['total']} public groups"
    else:
        side = f"lower than {r['total'] - r['below']} of {r['total']} public groups"
    tone = "worse" if (r["worse_than_median"] == higher_is_worse) else "better"
    return f"{side} &mdash; {tone} than the Index median of {pct(r['median'])}"


# ---------------------------------------------------------------------------
# formatting
# ---------------------------------------------------------------------------
def pct(v: float | None, dash: str = "&mdash;") -> str:
    return dash if v is None else f"{v * 100:.0f}%"


def money(v: float | None) -> str:
    return "&mdash;" if v is None else f"${v:,.2f}"


# ---------------------------------------------------------------------------
# chart
# ---------------------------------------------------------------------------
def curve_svg(curve: list[dict]) -> str:
    """Bars: share of spend per run-length fifth. Line: resolve rate, when outcomes exist."""
    if not curve:
        return ""
    W, H, PAD_B, PAD_T = 720, 300, 56, 30
    floor, ceil = H - PAD_B, PAD_T
    span = floor - ceil
    shares = [c.get("cost_share") or 0 for c in curve]
    top = max(max(shares), 0.01) * 1.25
    slot = W / len(curve)
    bw = slot * 0.52

    parts = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
             f'aria-label="Share of spend and resolve rate by run-length fifth">',
             f'<line x1="20" y1="{floor}" x2="{W - 20}" y2="{floor}" stroke="{INK}" stroke-width="2"/>',
             f'<g font-family="Barlow, system-ui, sans-serif" font-size="14" font-weight="600" fill="{INK}">']

    for i, c in enumerate(curve):
        share = c.get("cost_share") or 0
        h = max((share / top) * span, 2)
        x, y = i * slot + (slot - bw) / 2, floor - h
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{YELLOW}"/>')
        parts.append(f'<text x="{x + bw / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle">{pct(share)}</text>')
        label = f"{c['steps_lo']}&ndash;{c['steps_hi']} steps"
        parts.append(f'<text x="{x + bw / 2:.1f}" y="{floor + 20}" text-anchor="middle" '
                     f'fill="{MUTE}" font-weight="500" font-size="13">{label}</text>')
        parts.append(f'<text x="{x + bw / 2:.1f}" y="{floor + 38}" text-anchor="middle" '
                     f'fill="{MUTE}" font-weight="500" font-size="13">{c["n"]} runs</text>')

    resolves = [c.get("resolve") for c in curve]
    if any(r is not None for r in resolves):
        pts, dots = [], []
        rmax = max(r for r in resolves if r is not None) or 1
        for i, r in enumerate(resolves):
            if r is None:
                continue
            cx = i * slot + slot / 2
            cy = floor - (r / max(rmax * 1.25, 0.01)) * span
            pts.append(f"{cx:.1f},{cy:.1f}")
            dots.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{INK}"/>'
                        f'<text x="{cx:.1f}" y="{cy - 12:.1f}" text-anchor="middle">{pct(r)}</text>')
        if len(pts) > 1:
            parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{INK}" stroke-width="3"/>')
        parts += dots
    parts.append("</g></svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------
def build(audit: dict, index: dict, org: str) -> str:
    curve = audit.get("curve") or []
    tail = next((c for c in curve if c["q"] == 5), None)
    tail_share = tail.get("cost_share") if tail else None
    waste_share, sunk_share = audit.get("waste_share"), audit.get("sunk_share")
    has_outcomes = any(c.get("resolve") is not None for c in curve)

    # Resolved per dollar, shortest fifth against longest: the number a step budget is set from.
    first = next((c for c in curve if c["q"] == 1), None)
    rpd_lo = first.get("resolved_per_dollar") if first else None
    rpd_hi = tail.get("resolved_per_dollar") if tail else None
    yield_line = ""
    if rpd_lo and rpd_hi:
        yield_line = (f" In your own runs a dollar spent in the longest fifth returns "
                      f"<b>{rpd_lo / rpd_hi:.0f}&times; fewer</b> resolved tasks than a dollar in the shortest.")
    elif rpd_lo and rpd_hi == 0:
        # The strongest version of the same finding, and the one a ratio cannot express.
        yield_line = (" In your own runs the longest fifth resolved <b>nothing at all</b>, so every dollar "
                      f"of the {pct(tail_share)} it consumed bought no completed task.")

    dist = index_distributions(index)
    r_tail = rank(tail_share, dist["tail_share"])
    r_waste = rank(waste_share, dist["waste_share"])
    r_sunk = rank(sunk_share, dist["sunk_share"])

    subs = audit.get("submissions", {})
    total = audit.get("total_cost") or 0
    # The four buckets, drawn as if disjoint. The shares are measured separately and can
    # overlap (a long run can also be a failed run), so the remainder is a residual.
    rest = max(1 - (waste_share or 0) - (sunk_share or 0) - (tail_share or 0), 0)

    detector_rows = []
    for name, s in sorted(subs.items(), key=lambda kv: -(kv[1].get("waste_cost") or 0)):
        for det, v in sorted(s.get("by_detector", {}).items()):
            detector_rows.append((escape(name), escape(det), v.get("share_of_trajs"), v.get("cost")))

    head_rows = "".join(
        f"<tr><th scope='row'>{escape(name)}</th><td>{s['trajectories']:,}</td><td>{money(s.get('total_cost'))}</td>"
        f"<td>{s.get('mean_steps', 0):.0f}</td><td>{pct(s.get('waste_share'))}</td><td>{pct(s.get('sunk_share'))}</td>"
        f"<td>{pct(s.get('resolve_rate'))}</td></tr>"
        for name, s in sorted(subs.items(), key=lambda kv: -(kv[1].get("total_cost") or 0)))

    det_rows = "".join(
        f"<tr><th scope='row'>{n}</th><td>{d}</td><td>{pct(share)}</td><td>{money(cost)}</td></tr>"
        for n, d, share, cost in detector_rows) or "<tr><td colspan='4'>No detector fired.</td></tr>"

    outcomes_note = "" if has_outcomes else f"""
<div class="callout">
<b>Your traces carry no task outcomes, so the resolve line is blank.</b>
The cost curve above is real; what it cannot tell you is whether the long runs are buying
anything. Outcome labels are the single highest-value thing you can add &mdash; a boolean per run,
joined from CI, a test result, or a merge. With them, this page reports resolved-per-dollar by
run length, which is the number a step budget is actually set from.
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent spend benchmark &mdash; {escape(org)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow:wght@400;500;600&family=Barlow+Condensed:wght@600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:{PAPER};color:{INK};font-family:Barlow,system-ui,-apple-system,sans-serif;
 font-size:16px;line-height:1.55;font-variant-numeric:tabular-nums}}
.wrap{{max-width:860px;margin:0 auto;padding:42px 24px 80px}}
h1,h2{{font-family:"Barlow Condensed",Barlow,sans-serif;font-weight:700;line-height:1;margin:0;letter-spacing:-.01em}}
h1{{font-size:46px}}
h2{{font-size:30px;margin:52px 0 14px;padding-top:22px;border-top:2px solid {INK}}}
p{{margin:0 0 14px}}
.meta{{display:flex;gap:22px;flex-wrap:wrap;margin-top:18px;padding-top:14px;border-top:1px solid {RULE};
 font-size:14.5px;color:{MUTE}}} .meta b{{color:{INK}}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin:26px 0 10px;border:2px solid {INK};border-radius:8px;overflow:hidden}}
.stat{{padding:18px 18px 16px;border-right:1px solid {RULE}}} .stat:last-child{{border-right:0}}
.stat .v{{font-family:"Barlow Condensed",Barlow,sans-serif;font-size:52px;font-weight:700;line-height:1}}
.stat .k{{font-weight:600;margin-top:6px}} .stat .c{{font-size:13.5px;color:{MUTE};margin-top:5px;line-height:1.4}}
.bar{{display:flex;height:44px;border:2px solid {INK};border-radius:6px;overflow:hidden;margin-top:22px;font-size:14px;font-weight:600}}
.bar div{{display:flex;align-items:center;justify-content:center;min-width:0}}
.leg{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:14px;font-size:14px;color:{MUTE}}}
.leg b{{display:block;color:{INK};font-size:15px}}
.sw{{display:inline-block;width:11px;height:11px;border:1px solid {INK};margin-right:6px}}
table{{width:100%;border-collapse:collapse;margin-top:18px;font-size:15px}}
th,td{{text-align:left;padding:9px 12px 9px 0;border-bottom:1px solid {RULE};vertical-align:top}}
thead th{{border-bottom:2px solid {INK};font-family:"Barlow Condensed",Barlow,sans-serif;font-size:19px;font-weight:600}}
td{{color:#3B4257}}
.callout{{background:{PANEL};border-left:4px solid {YELLOW};padding:15px 17px;margin-top:20px;font-size:15px}}
.cap{{font-size:13.5px;color:{MUTE};margin-top:10px;line-height:1.5}}
.chart{{border:1px solid {RULE};border-radius:8px;padding:14px;margin-top:20px}}
svg{{display:block;width:100%;height:auto}}
@media (max-width:640px){{.stats,.leg{{grid-template-columns:1fr}}.stat{{border-right:0;border-bottom:1px solid {RULE}}}}}
@media print{{.wrap{{padding:0}}h2{{break-after:avoid}}}}
</style></head><body><div class="wrap">

<h1>Where your agent spend went</h1>
<div class="meta">
<span>prepared for <b>{escape(org)}</b></span>
<span>runs <b>{audit.get('trajectories', 0):,}</b></span>
<span>submissions <b>{len(subs)}</b></span>
<span>estimated spend <b>{money(total)}</b></span>
<span>generated <b>{date.today().isoformat()}</b></span>
</div>

<div class="stats">
<div class="stat"><div class="v">{pct(tail_share)}</div><div class="k">of spend in your longest fifth of runs</div>
<div class="c">{phrase(r_tail)}</div></div>
<div class="stat"><div class="v">{pct(waste_share)}</div><div class="k">mechanical waste</div>
<div class="c">{phrase(r_waste)}</div></div>
<div class="stat"><div class="v">{pct(sunk_share)}</div><div class="k">spent on runs that ended without a result</div>
<div class="c">{phrase(r_sunk)}</div></div>
</div>
<p class="cap">Compared against the {len(index.get('groups', []))} dataset/model/scaffold groups in the
Agent Waste Index, edition 1 ({index.get('total_runs', 0):,} public runs). Mechanical waste counts loops,
blind retries and oversized tool output on the same basis in both, so the comparison is like for like.</p>

<h2>Cost by run length</h2>
<div class="chart">{curve_svg(curve)}</div>
<p class="cap">Your runs, ordered by step count and split into five equal-sized buckets. Bars are each
bucket's share of your estimated spend. In the Index the longest fifth takes 40% of spend and returns
8&ndash;285&times; fewer resolved tasks per dollar than the shortest.{yield_line}</p>
{outcomes_note}

<h2>The four buckets</h2>
<div class="bar">
<div style="width:{rest * 100:.1f}%;background:{PAPER}">{pct(rest)}</div>
<div style="width:{(waste_share or 0) * 100:.1f}%;background:{YELLOW}">{pct(waste_share)}</div>
<div style="width:{(sunk_share or 0) * 100:.1f}%;background:{RED};color:#fff">{pct(sunk_share)}</div>
<div style="width:{(tail_share or 0) * 100:.1f}%;background:{INK};color:#fff">{pct(tail_share)}</div>
</div>
<div class="leg">
<div><span class="sw" style="background:{PAPER}"></span><b>The rest</b>The first four fifths of runs, minus the waste.</div>
<div><span class="sw" style="background:{YELLOW}"></span><b>Mechanical waste</b>Loops, blind retries, oversized tool output.</div>
<div><span class="sw" style="background:{RED}"></span><b>Failed runs</b>Hit a cap, exhausted context, cut off.</div>
<div><span class="sw" style="background:{INK}"></span><b>Low-yield tail</b>Your longest fifth of runs.</div>
</div>
<p class="cap">The three waste shares are measured separately and can overlap &mdash; a long run can also be a
failed run &mdash; so the bar draws them as disjoint and the first bucket is the remainder.</p>

<h2>By submission</h2>
<table><thead><tr><th>submission</th><th>runs</th><th>cost</th><th>mean steps</th><th>mech waste</th><th>failed-run spend</th><th>resolve</th></tr></thead>
<tbody>{head_rows}</tbody></table>

<h2>What fired</h2>
<table><thead><tr><th>submission</th><th>detector</th><th>share of runs</th><th>cost</th></tr></thead>
<tbody>{det_rows}</tbody></table>
<p class="cap">Edit thrash (T13) is listed when it fires but is not counted in mechanical waste or in
&ldquo;any finding&rdquo;: it flags ordinary edit-test-edit cycles too often to price. The Index excludes it
on the same grounds.</p>

<h2>Reading this</h2>
<p>Costs come from each trajectory's own reported cost where the traces carry one, and from tokens or
characters otherwise. The Index estimates cost from characters at Sonnet-class rates. Absolute dollars are
therefore not comparable between the two; the shares and the orderings are, which is why every
comparison above is a percentage.</p>
<p>Run counts matter here. The Index requires 200 runs per bucket before it reports a quintile;
this page reports from 25 runs total, because it is your own traffic rather than a published claim.
Under a few hundred runs, read the shape and ignore small differences between adjacent buckets.</p>
<p class="cap">Generated locally by metermaid. Nothing in this report left your machine.
Method, caveats and retractions for the Index: <a href="https://metermaid.ai/agent-waste-index.html">metermaid.ai/agent-waste-index.html</a>.</p>

</div></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description="Benchmark one trajectory audit against the Agent Waste Index.")
    ap.add_argument("audit", help="trajectory-audit.json written by trajectory_audit.py")
    ap.add_argument("--index", default="report/index.json", help="the Index to compare against")
    ap.add_argument("--out", default="benchmark.html")
    ap.add_argument("--org", default="your team", help="name to put on the report")
    a = ap.parse_args()

    audit = json.loads(Path(a.audit).read_text(encoding="utf-8"))
    index_path = Path(a.index)
    if not index_path.exists():
        raise SystemExit(f"{index_path} not found — run `python pipeline.py report`, or pass --index")
    index = json.loads(index_path.read_text(encoding="utf-8"))

    if not audit.get("curve"):
        print(f"note: no run-length curve in {a.audit} — under {25} runs, or produced by an older "
              f"trajectory_audit.py. The report will still show shares and detectors.")

    out = Path(a.out)
    out.write_text(build(audit, index, a.org), encoding="utf-8")
    print(f"Wrote {out} — {audit.get('trajectories', 0):,} runs against "
          f"{index.get('total_runs', 0):,} public runs.")


if __name__ == "__main__":
    main()
