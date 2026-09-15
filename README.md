# metermaid audit

Open-source tools behind [the Agent Waste Index](https://metermaid.ai/agent-waste-index.html): where AI agent spend goes, what it wasted, and what to change. Everything runs locally; keys and traces never leave your machine.

## Tools

| file | what it does |
|---|---|
| `metermaid_audit.py` | Spend audit against the Anthropic and OpenAI admin APIs (read-only). Prices over-tier models, missing prompt caching, batch-eligible jobs, spend spikes, unowned keys. `--anon` hashes every id so the output is safe to share. |
| `trajectory_audit.py` | Trace-level audit over agent trajectory files (SWE-agent, mini-swe-agent, OpenHands, message lists). Loops, blind retries, oversized tool output, edit thrash, runs that ended without a result. |
| `compare.py` | Baseline against candidate fixes on the same tasks, with the combined configuration as the authoritative number: paired cohorts, every attempt counted, unknown outcomes kept unknown, a quality gate, netted overhead, a bootstrap interval, and no adding of individual fixes. |
| `benchmark.py` | Turns one trajectory audit into a report positioned against the Index: cost by run length, the four-bucket split, and where each number sits among the Index's 29 public groups. Reads only the aggregates, writes one self-contained HTML page. |
| `pipeline.py` | The scaled pipeline: streams trajectory datasets from Hugging Face, parses nine formats, detects at ingest, writes Parquet, reports with DuckDB. Produces the Index. |
| `hf_pull.py`, `hf_batch.py` | Earlier per-file tooling for pulling Hugging Face trajectory datasets and sampling raw rows for new parsers. `pipeline.py` supersedes them for analysis. |
| `ratecard.json` | Per-model prices used by the spend audit. Carries a `price_version` and a `verified_on` date per model; the audit prints the version in every report and lists any price it used that is unverified or older than 90 days. Check those against the provider's pricing page before sharing an audit. |
| `keymap.example.json` | Map key / project ids to agents and owners. Copy to `keymap.json`. |
| `share.py` | Builds `share.json`, the only audit output meant to leave the machine: allowlisted aggregates with pseudonymised ids. Used by `--share` on both auditors. |
| `supported.json` | The claims ledger: what these tools do today, and the phrases the README, launch copy and website must not use because the thing does not exist. The tests enforce it against this repository's copy. |
| `schema.py` | The task/attempt/event records the trajectory audit writes locally (`attempts.jsonl`, `tasks.jsonl`, optional `events.jsonl`): identity rules, outcome provenance, and cost per successful task with every attempt counted. |

## Spend audit

```bash
pip install requests
cp keymap.example.json keymap.json
export ANTHROPIC_ADMIN_KEY=sk-ant-admin-...   # Console → Settings → Admin keys
export OPENAI_ADMIN_KEY=sk-admin-...          # platform.openai.com → Organization → Admin keys
python metermaid_audit.py --days 30 --anon
```

Reads usage (daily for the window, hourly for the last 7 days) and cost reports, prices usage from `ratecard.json`, and writes `audit/audit.md` and `audit/audit.json`. Each finding's dollar figure is labelled *observed* or *modeled* with the assumption it rests on, and the headline is a range (largest single finding to the capped sum) because findings on the same key overlap and are never added up. No keys? `--demo` runs on synthetic data.

### Check the cost-report unit against your own usage

The provider-reported cost line rests on an assumption about the unit each cost endpoint
returns (Anthropic: a decimal string in cents; OpenAI: dollars). Settle it against your own
numbers in one command:

```bash
ANTHROPIC_ADMIN_KEY=sk-ant-admin-... python metermaid_audit.py --probe
```

It fetches the last three full days of usage and cost, prices the usage with the rate card,
reads the cost report both ways, and says which reading matches, with the raw rows printed
(ids stripped) so the response shape is on record. Paste the output into an issue if it says
CONTRADICTS. `--days N` widens the window up to 7.

Status: the Anthropic reading (cents) was verified this way on 2026-09-15, ratio 1.00 to the
usage-priced estimate. The OpenAI reading (dollars) has not been probed yet.

## Trajectory audit

```bash
python trajectory_audit.py path/to/trajectories --label-by-parent --out ./traj-audit
```

Detectors: identical action three or more times with no state-changing action between (loop); identical action right after an error (blind retry); any observation over 20,000 characters (oversized tool output, re-sent every later step); runs that ended without a submit, hit the context limit, or were cut off.

Mechanical waste is the first three. Edit thrash (same file edited six or more times) is reported as its own line but not costed and not counted as a finding — it flags ordinary iterative editing too often. `pipeline.py` uses the same basis, so your number is comparable to the Index.

With 25 runs or more the audit also computes your **run-length curve**: runs ordered by step count, split into five buckets the same way the Index splits them, with each bucket's share of spend and its resolve rate. The curve is computed from your runs on your machine and only the five aggregate rows are written to the report — per-run rows never leave the audit.

### Tasks and attempts

A run is an attempt; the task is every attempt at the same job, restarts included. The audit
groups attempts by an explicit id on the record (`instance_id`, `task_id`, `problem_id`,
`issue_id`, or whatever `--task-id-field` names), else by file stem. It never groups by text
similarity. Attempts are ordered by an explicit index or timestamp when the record carries one,
else by path. The report's Tasks section gives tasks, attempts, how many tasks were restarted,
what the attempts after the first cost, how many leading steps a restart repeated from the
previous attempt, and cost per successful task with every attempt in the numerator — undefined,
not zero, when nothing succeeded or nothing carries an outcome.

Outcomes are `success`, `failure` or `unknown`, read from `resolved`, `target`, `success`,
`verified` or `passed`; a missing label is unknown, never failure, and the report says which field
the outcomes came from. The Intake section counts records parsed, files not parsed, and duplicate
attempt ids dropped. `attempts.jsonl` and `tasks.jsonl` are written next to the report; `--events`
adds `events.jsonl` with one row per step (action, sizes and hashes, not the tool output). All of
these stay local.

## Compare a fix against the baseline

Run the trajectory audit once on the workflow as it was and once per configuration under test,
then:

```bash
python compare.py --baseline audit-before \
                  --candidate cache=audit-cache --candidate trim=audit-trim \
                  --combined both=audit-both --overhead cache=40 --out compare
```

Arms are compared on the tasks present in every arm, paired by task id, and coverage is printed.
Cost counts every attempt at a task. Success rate is over tasks with a known outcome and the
unknown count sits beside it; no successes gives an undefined ratio, not zero. A candidate whose
success rate falls more than `--quality-tolerance` points (default 2) is rejected however much it
saves; `--overhead` nets out what the fix costs to run; a paired bootstrap gives a 90% interval on
the cost change; a cohort under `--min-tasks` (default 20) is inconclusive. Each arm ends as
verified, inconclusive or rejected with the reasons listed.

Individual fixes are never added. The combined arm is the claim; the naive sum of the individual
arms is printed beside it only to make the overlap visible. Latency is not in trajectory records
and is reported as such.

## Benchmark against the Index

```bash
python trajectory_audit.py ./your-traces --out ./traj-audit
python benchmark.py traj-audit/trajectory-audit.json --org "Acme" --out benchmark.html
```

Writes one self-contained page: your spend by run length, the split between productive spend and
the three kinds of waste, and where each of your numbers falls among the 29 public groups in the
Index. Absolute dollars are not comparable between a local audit (priced from the traces' own
cost) and the Index (estimated from characters), so every comparison is a share.

If your traces carry no task outcomes the cost curve still works and the report says so plainly:
without outcomes there is no resolve rate, and no way to tell whether the long runs bought
anything. Adding a boolean per run — from CI, a test result, a merge — is the single highest-value
thing you can do to your traces.

## Pipeline and the Index

```bash
python -m pip install datasets pyarrow duckdb
python pipeline.py sweep --limit 20000      # every registered dataset/config/split -> data/runs/*.parquet
python pipeline.py sweep --limit 20000 --resume   # after an interruption: skips splits whose shard exists
python pipeline.py report                   # -> report/index.md, report/index.json
python pipeline.py ingest <dataset> --config <cfg> --split <split> --limit N
python pipeline.py ingest-json samples/*.json   # parse raw rows to test a new format
```

Registered datasets, formats, and end-of-run rules live in `REGISTRY` and the parsers at the top of `pipeline.py`. Edition 1.1 covers 341,054 runs from 11 datasets — 29 dataset/model/scaffold groups, 16 model labels, 4 scaffold families. The report is in `report/`, with method, caveats and retractions in [`report/notes.md`](report/notes.md).

Headline findings are in the Index; method, caveats and retractions are in [`report/notes.md`](report/notes.md) — read those before quoting anything. Dollars in the Index are estimated (characters/4, Sonnet-class rates, with and without cached input pricing); quote the percentages.

## What is supported today

`supported.json` is the list. In one line: spend audit against the **Anthropic** and **OpenAI**
admin APIs, read-only, from your machine; trajectory audit over **SWE-agent**, **mini-swe-agent**,
**OpenHands** and generic **message lists**; outputs are local markdown and JSON reports,
`benchmark.html`, and `share.json`. Nothing else. If a page or a post names another provider,
trace source, outcome source or product feature, it is describing something that does not exist
yet, and the test suite fails on this repository's copy when that happens.

## Tests

```bash
python -m unittest discover -s tests -v     # or: python tests/test_smoke.py
```

Standard library only; the pipeline report tests skip unless `duckdb` and `pyarrow` are installed.
They cover the detectors, the spend audit's `--demo` and `--anon` paths, the shared
mechanical-waste basis that makes a local audit comparable to the Index, the run-length curve and
the benchmark report built from it, and the checked-in report agreeing with the numbers quoted in
this README, `report/notes.md` and `launch.md`.
CI runs them on every push and pull request.

## Sharing results

Neither local report is meant to leave your machine. `audit/audit.json` carries per-key spend
under your own labels; `traj-audit/trajectory-audit.json` carries run ids (often repo and issue
names) and the worst runs' commands. `--anon` on the spend audit hashes key, workspace and
project ids and drops owner emails in that local report; the trajectory audit's local report
is never anonymised.

The file to send is `share.json`, written by `--share` on either tool. It is built by allowlist
from the local result: totals, shares, the five run-length rows, per-detector counts and costs,
findings with their evidence, and pseudonymised submission, agent and key ids. It never carries
per-run rows, run ids, commands, prompts, tool output, file paths, owner emails, or raw
key/workspace/project ids, and it says so inside the file. The tool prints exactly what the
file contains before it writes it.

```bash
python trajectory_audit.py ./your-traces --share --salt "$METERMAID_SALT"
python metermaid_audit.py --share --salt "$METERMAID_SALT"
```

Fix `--salt` and the same submission or key hashes to the same pseudonym next month, so two
share files can be compared. Omit it for a one-off random salt. Keep the salt like a password;
it is never written to any file.

You can generate your own position against the Index locally with `benchmark.py` — nothing
needs to be sent. If you would rather we read it, send `share.json` via the form at
metermaid.ai and we will go through it with you.

## Data sources (edition 1)

SWE-bench/SWE-smith-trajectories, nvidia/Open-SWE-Traces, nebius/SWE-agent-trajectories, nebius/SWE-rebench-openhands-trajectories, nvidia/SWE-Hero and SWE-Zero, SWE-Gym/OpenHands-Sampled-Trajectories, thoughtworks/agentic-coding-trajectories, open-thoughts/AgentTrove, ricdomolm/mini-coder-trajs-400k, AlienKevin/SWE-ZERO-12M-trajectories. The SWE-bench leaderboard S3 bucket and Princeton HAL traces are access-restricted; `download_logs.py` is a signed-request patch of the SWE-bench helper kept in case that changes.

MIT.
