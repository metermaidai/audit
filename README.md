# metermaid audit

Open-source tools behind [the Agent Waste Index](https://metermaid.ai/agent-waste-index.html): where AI agent spend goes, what it wasted, and what to change. Everything runs locally; keys and traces never leave your machine.

## Tools

| file | what it does |
|---|---|
| `metermaid_audit.py` | Spend audit against the Anthropic and OpenAI admin APIs (read-only). Prices over-tier models, missing prompt caching, batch-eligible jobs, spend spikes, unowned keys. `--anon` hashes every id so the output is safe to share. |
| `trajectory_audit.py` | Trace-level audit over agent trajectory files (SWE-agent, mini-swe-agent, OpenHands, message lists). Loops, blind retries, oversized tool output, edit thrash, runs that ended without a result. |
| `pipeline.py` | The scaled pipeline: streams trajectory datasets from Hugging Face, parses nine formats, detects at ingest, writes Parquet, reports with DuckDB. Produces the Index. |
| `hf_pull.py`, `hf_batch.py` | Earlier per-file tooling for pulling Hugging Face trajectory datasets and sampling raw rows for new parsers. `pipeline.py` supersedes them for analysis. |
| `ratecard.json` | Per-model prices used by the spend audit. Verify against provider pricing pages before sharing an audit. |
| `keymap.example.json` | Map key / project ids to agents and owners. Copy to `keymap.json`. |

## Spend audit

```bash
pip install requests
cp keymap.example.json keymap.json
export ANTHROPIC_ADMIN_KEY=sk-ant-admin-...   # Console → Settings → Admin keys
export OPENAI_ADMIN_KEY=sk-admin-...          # platform.openai.com → Organization → Admin keys
python metermaid_audit.py --days 30 --anon
```

Reads usage (daily for the window, hourly for the last 7 days) and cost reports, prices usage from `ratecard.json`, and writes `audit/audit.md` and `audit/audit.json`. No keys? `--demo` runs on synthetic data.

## Trajectory audit

```bash
python trajectory_audit.py path/to/trajectories --label-by-parent --out ./traj-audit
```

Detectors: identical action three or more times with no state-changing action between (loop); identical action right after an error (blind retry); any observation over 20,000 characters (oversized tool output, re-sent every later step); runs that ended without a submit, hit the context limit, or were cut off.

Mechanical waste is the first three. Edit thrash (same file edited six or more times) is reported as its own line but not costed and not counted as a finding — it flags ordinary iterative editing too often. `pipeline.py` uses the same basis, so your number is comparable to the Index.

## Pipeline and the Index

```bash
python -m pip install datasets pyarrow duckdb
python pipeline.py sweep --limit 20000      # every registered dataset/config/split -> data/runs/*.parquet
python pipeline.py report                   # -> report/index.md, report/index.json
python pipeline.py ingest <dataset> --config <cfg> --split <split> --limit N
python pipeline.py ingest-json samples/*.json   # parse raw rows to test a new format
```

Registered datasets, formats, and end-of-run rules live in `REGISTRY` and the parsers at the top of `pipeline.py`. Edition 1 covers 341,054 runs from 11 datasets — 29 dataset/model/scaffold groups, 16 model labels, 4 scaffold families. The report is in `report/`, with method, caveats and retractions in [`report/notes.md`](report/notes.md).

Headline findings are in the Index; method, caveats and retractions are in [`report/notes.md`](report/notes.md) — read those before quoting anything. Dollars in the Index are estimated (characters/4, Sonnet-class rates, with and without cached input pricing); quote the percentages.

## Tests

```bash
python -m unittest discover -s tests -v     # or: python tests/test_smoke.py
```

Standard library only; the pipeline report tests skip unless `duckdb` and `pyarrow` are installed.
They cover the detectors, the spend audit's `--demo` and `--anon` paths, the shared
mechanical-waste basis that makes a local audit comparable to the Index, and the checked-in
report agreeing with the numbers quoted in this README, `report/notes.md` and `launch.md`.
CI runs them on every push and pull request.

## Sharing results

`--anon` on the spend audit hashes key, workspace, and project ids and drops owner emails. Send `audit/audit.json` or `traj-audit/trajectory-audit.json` via the form at metermaid.ai and get your resolve-by-length curve and your position against the Index.

## Data sources (edition 1)

SWE-bench/SWE-smith-trajectories, nvidia/Open-SWE-Traces, nebius/SWE-agent-trajectories, nebius/SWE-rebench-openhands-trajectories, nvidia/SWE-Hero and SWE-Zero, SWE-Gym/OpenHands-Sampled-Trajectories, thoughtworks/agentic-coding-trajectories, open-thoughts/AgentTrove, ricdomolm/mini-coder-trajs-400k, AlienKevin/SWE-ZERO-12M-trajectories. The SWE-bench leaderboard S3 bucket and Princeton HAL traces are access-restricted; `download_logs.py` is a signed-request patch of the SWE-bench helper kept in case that changes.

MIT.
