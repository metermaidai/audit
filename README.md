# metermaid audit — Phase 0

One-page audit of AI agent spend from the Anthropic and OpenAI admin APIs.
Runs on your machine. Keys never leave it. Output is `audit.md` + `audit.json`.

## Run

```bash
pip install requests
cp keymap.example.json keymap.json      # map keys/projects to agents + owners (optional but recommended)

export ANTHROPIC_ADMIN_KEY=sk-ant-admin-...   # Console → Settings → Admin keys (org admin only)
export OPENAI_ADMIN_KEY=sk-admin-...          # platform.openai.com → Organization → Admin keys

python metermaid_audit.py --days 30 --out ./audit
```

No keys handy? `python metermaid_audit.py --demo` runs on synthetic data.

## What it reads

- Anthropic: `GET /v1/organizations/usage_report/messages` (hourly, grouped by key/workspace/model/tier) and `GET /v1/organizations/cost_report` (daily)
- OpenAI: `GET /v1/organization/usage/completions` (hourly, grouped by model/project/key/batch) and `GET /v1/organization/costs` (daily)

Both require an org-level admin key. Both are read-only.

## Detectors (usage-only set)

| ID | Finding | Priced how |
|---|---|---|
| L01 | Frontier model on short, high-volume traffic | frontier cost − same tokens at mid-tier, × 50% substitutable share |
| L02 | Spend with no named owner | governance, not priced |
| L05 | Prompt caching unused | 50% of uncached input × (input − cache-read price) |
| L06 | Input tokens/request growing with flat volume | excess tokens × input price |
| L07 | Daily spend spike > mean + 3σ | excess over mean |
| L10 | Bursty workload not on batch pricing | spend × 50% |

Thresholds are defaults; tune in `analyze()`. Prices live in `ratecard.json` — verify against provider pricing pages before you hand an audit to anyone.

## Known limits

- Estimates are from usage × rate card; `cost_report`/`costs` totals are printed alongside for reconciliation.
- Unknown model ids are priced at a tier reference price and listed at the bottom of the report.
- No trace-level detectors (loops, retries, context bloat) — that's Phase 2.
