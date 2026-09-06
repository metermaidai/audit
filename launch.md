# Launch copy — paste-ready

Every number below is from `report/index.json` (edition 1, 341,054 runs). Method, caveats and
retractions: [`report/notes.md`](report/notes.md). Cost is estimated (chars/4 at Sonnet-class
rates) — quote percentages, never dollars.

**Do not reuse the 4,000-run pilot copy.** Its headline ("runs with any finding resolve at half
the rate, in every group") does not survive the full set, and its per-run dollar figures were
withdrawn. See the retractions section in notes.md before answering questions about it.

---

## 1. README section (add under the title)

### What we found in 341,054 public coding-agent runs

We ran the trajectory detectors over 341,054 runs from 11 public trajectory datasets — 29
dataset/model/scaffold groups, 4 scaffold families, from 2024 Llama agents to Qwen3-Coder-480B and
Claude 3.7 Sonnet. Every run is scored at ingest by the same detectors on the same pricing basis;
groups are capped at the first 20,000 runs of each dataset/config/split, so the larger datasets
are a head sample, not their entirety.

Three things stood out.

**1. Mechanical waste is small, and loops are basically a solved problem.** Across the whole set,
loops, blind retries and context bloat account for 4% of estimated spend. Degenerate loops are a
weak-model artifact: 14% of runs on swe-agent-llama-70b and 18% on llama-8b, against 0.4–0.5% on
Claude 3.7 Sonnet and 0.0–1.3% on Qwen3-Coder-480B. Blind retries follow the same shape (22% and
31% on the Llama agents; under 1% on Claude 3.7). If you are still writing loop detectors for a
frontier model, you are solving 2024's problem.

**2. Oversized tool output is a scaffold property, not a model property.** Open-SWE-Traces v1.1
runs the same trace version through three scaffolds, so the model is held constant:

| scaffold | runs | median steps | runs carrying a >20k-char observation |
|---|---:|---:|---:|
| minisweagent | 20,000 | 51 | 0.1% |
| openhands | 20,000 | 77 | 49.9% |
| sweagent | 20,000 | 76 | 54.8% |

Across all five mini-swe-agent groups in the set, oversized observations stay at or below 0.2%,
while openhands groups run 7–72%. The likely cause is an output cap in the scaffold rather than
tidier models — worth confirming against the scaffold source before you quote a mechanism — but
the shape of the result is not subtle, and the capped scaffold's runs are *shorter*, not longer.

**3. The money is in run length, and the long tail buys almost nothing.** Split each group's runs
into five equal-count buckets by step count. The longest bucket takes 40% of estimated spend
across the whole set (21–72% by group, median 50%) and is the worst bucket per task solved:
resolved-per-dollar is lowest in the longest quintile in 13 of the 15 groups that carry resolve
labels, by 8× to 285×. Resolve rate itself falls from the shortest to the longest quintile in 14
of 15. Whatever else you tune, a step budget is the lever with the most money behind it.

**Caveats.** No public dataset here carries per-run cost, so dollars are estimated from characters
at Sonnet-class rates — read the percentages. Task mix differs by group, so resolve rates are
comparable within a group, not across groups. `thoughtworks/agentic-coding-trajectories` resamples
populations already in the set; don't pool it with them. Full list in
[`report/notes.md`](report/notes.md).

**Retracted from the pilot.** An earlier 4,000-run version of this reported that runs tripping any
detector resolved at ~half the rate of clean runs in every group, and pitched it as a mid-run kill
signal. At full scale that holds only for weak models (0.16–0.25× on Llama and gpt-4o) and
reverses on SWE-smith Claude 3.5 Sonnet (1.10–1.22×) and mini-coder-trajs-400k (1.18×) — 15 of 20
groups worse when flagged, 5 better. Don't ship a kill switch on it without measuring your own
traffic.

Reproduce: `python pipeline.py sweep --limit 20000` then `python pipeline.py report`.

---

## 2. Show HN

**Title:** Show HN: Audit your AI agent spend locally – plus what 341,054 public agent runs showed

**Body:**

I built a small CLI that reads your Anthropic/OpenAI admin API on your own machine (nothing is
sent anywhere) and prices the waste: frontier models on short high-volume traffic, uncached
prompts, nightly jobs off batch pricing, keys with no owner.

Before asking anyone to run it on their own spend, I ran the trace-level detectors over 341,054
runs from 11 public trajectory datasets, 4 scaffold families (capped at 20k runs per
dataset/config/split). Findings:

- Mechanical waste (loops, blind retries, context bloat) is 4% of estimated spend. Degenerate
  loops are a weak-model artifact: 14–18% of runs on 2024 Llama agents, 0.4–0.5% on Claude 3.7.
- Oversized tool output is a scaffold choice. Same Open-SWE trace version through three scaffolds:
  0.1% of runs carry a >20k-char observation under mini-swe-agent, 50% under OpenHands, 55% under
  SWE-agent. The capped scaffold's runs are shorter, not longer.
- The real money is run length. The longest fifth of runs takes 40% of estimated spend and is the
  worst bucket per task solved in 13 of 15 groups with resolve labels — by 8× to 285×.

An earlier 4,000-run version of this claimed waste predicts failure everywhere. It doesn't: at
full scale that only holds on weak models and reverses on Claude 3.5 SWE-smith. That retraction
and the rest of the caveats are in report/notes.md in the repo.

Repo has both tools and the commands to reproduce the whole Index from public Hugging Face
datasets. Run the spend audit with `--anon` and post or send me the JSON and I'll reply with the
three biggest fixes; everyone who sends gets the aggregate benchmark back.

---

## 3. r/LLMDevs / r/LangChain

**Title:** I ran waste detectors over 341,054 public coding-agent runs. Loops are solved; run length is where the money goes.

**Body:**

Two scripts: one reads your Anthropic/OpenAI admin API locally and prices spend waste (over-tier
models, no caching, batch-eligible jobs, unowned keys); one runs trace-level detectors (loops,
blind retries, context bloat, abandoned runs) over agent trajectories.

Ran the second over 11 public datasets — 341,054 runs, 29 model/scaffold groups, capped at 20k
runs per dataset/config/split:

- Mechanical waste is 4% of estimated spend overall. Loops: 14% of runs on swe-agent-llama-70b,
  0.4% on Claude 3.7 Sonnet. Blind retries: 22% vs under 1%. That failure mode is gone at the
  frontier.
- Context bloat is the scaffold's fault, not the model's. Same Open-SWE v1.1 traces:
  mini-swe-agent 0.1% of runs with a >20k-char observation, OpenHands 50%, SWE-agent 55%.
- Run length dominates. The longest quintile takes 21–72% of a group's estimated spend (median
  50%) and returns 8–285× fewer resolved tasks per dollar than the shortest.

Also a retraction: an earlier 4,000-run cut of this said runs tripping any detector resolve at
half the rate, everywhere. At 341k that's true for weak models and *reverses* on Claude 3.5
SWE-smith. Details in report/notes.md.

Repo + reproduce commands in the comments. Run the spend audit with `--anon` on your own org and
post the JSON — I'll tell you what to fix.

---

## 4. X thread

1/ I ran waste detectors over 341,054 public AI coding-agent runs — 11 datasets, 29 model/scaffold
groups. Short version: the loop problem is solved. The run-length problem isn't.

2/ Degenerate loops and blind retries are a 2024 weak-model artifact. swe-agent-llama-70b: 14% of
runs loop, 22% blindly re-run a failing command. Claude 3.7 Sonnet: 0.4% and 0.5%.
Qwen3-Coder-480B: under 1.3%.

3/ Total mechanical waste across the whole set — loops, blind retries, oversized tool output —
is 4% of estimated spend. It is not where your money is going.

4/ Oversized tool output is a scaffold choice, not a model trait. Same Open-SWE v1.1 traces, three
scaffolds: 0.1% of runs carry a >20k-char observation under mini-swe-agent, 50% under OpenHands,
55% under SWE-agent. The capped one has *shorter* runs.

5/ Here's the money. Split each group's runs into fifths by step count. The longest fifth takes
40% of estimated spend across the set (up to 72% in a group) and returns 8–285× fewer resolved
tasks per dollar than the shortest fifth. 13 of 15 groups, same direction.

6/ A correction to my own earlier post: on 4,000 runs I said runs tripping any detector resolve at
half the rate, in every group. At 341k it only holds on weak models (0.16–0.25×) and reverses on
Claude 3.5 SWE-smith (up to 1.22×). Retracted, written up in the repo.

7/ Both tools are open: a local spend audit for your Anthropic/OpenAI org (nothing leaves your
machine) and the trajectory auditor. Reproduce commands in the README. Run the audit with --anon,
send me the JSON, I'll send back the fixes. [repo link]

---

## 5. Discord one-liner (LangChain, Latent Space)

Ran waste detectors over 341,054 public agent runs. Loops are a solved problem (14% of runs on
2024 Llama agents, 0.4% on Claude 3.7), mechanical waste is only 4% of spend, and the actual money
is run length — the longest fifth of runs takes 40% of estimated spend and returns up to 285×
fewer resolved tasks per dollar. Open tools + reproduce steps here: [repo link]. If you run the
spend audit on your org with --anon and DM me the JSON I'll send back the top fixes.
