# Launch copy — paste-ready

Every number below is from `report/index.json` (edition 1.1, 341,054 runs). Method, caveats and
retractions: [`report/notes.md`](report/notes.md). Cost is estimated (chars/4 at Sonnet-class
rates) — quote percentages, never dollars.

**Do not reuse the 4,000-run pilot copy.** Its headline ("runs with any finding resolve at half
the rate, in every group") does not survive the full set, and its per-run dollar figures were
withdrawn. See the retractions section in notes.md before answering questions about it.

---

## 0. Where to post, in what order, and how to behave there

Post everything on one day, a Tuesday, Wednesday or Thursday, between 8 and 10am US Eastern. That
is when Hacker News and the subreddits have the most readers and the front page turns over the
slowest. Do the inbox check first (the form's notification must land, not go to spam) because
every one of these sends people to the form.

| Order | Venue | What it is | What to post | House rules that matter |
|---|---|---|---|---|
| 1 | Hacker News, https://news.ycombinator.com/submit | The forum the engineers and founders we want read every morning. A "Show HN" is the convention for posting something you built; it gets its own list and the audience expects a maker in the comments. | Section 2. URL is the repo. | One submission, never a resubmit the same week. Do not ask anyone to upvote, do not post the link in group chats with "please upvote"; HN detects voting rings and buries the post. Reply to every comment for the first three hours. Lead with the retraction if anyone finds it first. |
| 2 | X, https://x.com | Where the AI engineering crowd argues. A numbered thread reads as a finding, a single tweet with a link reads as an ad. | Section 4, seven posts, the link only in the last one. | Post the thread as replies to your own first post. Quote-post it once later in the week with the one chart. |
| 3 | Bluesky | Same audience as X two years ago, smaller, friendlier to open-source posts. | Section 4 unchanged, 300-character limit per post. | Same as X. |
| 4 | Reddit r/LLMDevs, then r/LangChain a day later | Practitioner subreddits; posts with data and a repo do well, posts with a product name in the title do not. | Section 3. Title only, body text, and put the repo link in the first comment. | Never crosspost the same hour; the two mod teams both see it. Do not mention pricing or the pilot. If a mod removes it, message them, do not repost. |
| 5 | Reddit r/LocalLLaMA and r/ClaudeAI | Larger, noisier. LocalLLaMA cares about the Llama vs Qwen vs Claude loop rates; ClaudeAI cares about the Claude 3.7 numbers. | Section 3 with the title changed to the finding that community cares about (suggested titles below). | LocalLLaMA removes anything that reads as a SaaS pitch. Keep it to the public data and the open tools. |
| 6 | LinkedIn | Where the buyer (CTO, VP Eng, technical founder) reads. Different register: shorter, outcome first, no jargon. | Section 6. | No external link in the post body (LinkedIn suppresses reach); link in the first comment. |
| 7 | Hugging Face, https://huggingface.co/posts | The Index is built entirely on Hugging Face datasets. A post there reaches the people who published them and the people who train on them. | Section 7. | Tag the dataset authors by org name only if you are prepared for them to reply with corrections. That is the point. |
| 8 | Discord and Slack: LangChain, Latent Space, the SWE-bench/SWE-agent Discord, the OpenHands Slack | Communities around the scaffolds in the data. The OpenHands and SWE-agent people will care most about the oversized-output result, since it is about their code. | Section 5, one message, in the channel for sharing work, never in general. | One message per server. Answer questions in the thread. Do not DM people the link. |
| 9 | Newsletters: TLDR AI, Ben's Bites, Latent Space, The Sequence, Last Week in AI | They pick up things already doing well on HN or X. A two-line tip email the afternoon of the launch is enough. | Section 8. | Send the day of, not before. Do not follow up. |

Suggested community-specific titles for the Reddit variants:

- r/LocalLLaMA: *Loop and blind-retry rates across 341,054 public agent runs: 14% and 22% on
  Llama-70B SWE-agent, under 1.3% on Qwen3-Coder-480B, 0.4% on Claude 3.7*
- r/ClaudeAI: *Claude 3.7 Sonnet in 341,054 public coding-agent runs: loops in 0.4%, blind retries
  0.5%, but the longest fifth of runs still takes ~half the spend*
- r/MachineLearning (optional, with the `[P]` tag): *[P] Agent Waste Index: 341,054 public
  coding-agent trajectories scored for loops, retries, oversized output and run-length cost*

Where not to post: Product Hunt (wrong audience, wrong format for a finding), Lobsters (invite
only, and it dislikes anything commercial), Medium or dev.to (a repost adds nothing the Index
page does not already carry).

**What to say when someone challenges a number.** Point at `report/notes.md` and the reproduce
command. Every figure in the posts is in `report/index.json` and the tests fail if the copy
drifts from it. If they find a real error, say so in the thread, fix it in the repo, and add it
to the corrections list in notes.md. The five corrections already there are the credibility.

**What not to say.** No dollar figures (the cost basis is estimated). No "capping saves 44%". No
claim that a detector predicts failure. No provider, trace source or feature that is not in
`supported.json`: the test suite enforces that on this file.

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
resolved-per-dollar is lowest in the longest quintile in 16 of the 18 groups that carry resolve
labels, by 5× to 294×. Resolve rate itself falls from the shortest to the longest quintile in 17
of 18. Whatever else you tune, measure what the marginal step buys before you set a cap: that is
where the money sits, and a cap still pays for every step up to the cap, so the cap itself
needs its own test.

**Caveats.** No public dataset here carries per-run cost, so dollars are estimated from characters
at Sonnet-class rates — read the percentages. Task mix differs by group, so resolve rates are
comparable within a group, not across groups. `thoughtworks/agentic-coding-trajectories` resamples
populations already in the set; don't pool it with them. Full list in
[`report/notes.md`](report/notes.md).

**Retracted from the pilot.** An earlier 4,000-run version of this reported that runs tripping any
detector resolved at ~half the rate of clean runs in every group, and pitched it as a mid-run kill
signal. At full scale that holds only for weak models (0.16–0.25× on Llama and gpt-4o) and
reverses on SWE-smith Claude 3.5 Sonnet (1.10–1.22×) and mini-coder-trajs-400k (1.18×) — 18 of 23
groups worse when flagged, 5 better. Don't ship a kill switch on it without measuring your own
traffic.

Reproduce: `python pipeline.py sweep --limit 20000` then `python pipeline.py report`.

---

## 2. Show HN

**Title (74 chars; HN truncates at 80):** Show HN: Agent Waste Index – what 341,054 public coding-agent runs wasted

**URL:** https://github.com/metermaidai/audit (the repo, not the marketing page; the Index page is linked from the body)

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
  SWE-agent. The capped scaffold's runs are shorter, not longer. It also resolves fewer tasks on
  that version (30% against SWE-agent's 53%), so the cap is not free either.
- The real money is run length. The longest fifth of runs takes 40% of estimated spend and is the
  worst bucket per task solved in 16 of 18 groups with resolve labels — by 5× to 294×.

An earlier 4,000-run version of this claimed waste predicts failure everywhere. It doesn't: at
full scale that only holds on weak models and reverses on Claude 3.5 SWE-smith. That retraction
and the rest of the caveats are in report/notes.md in the repo.

Repo has both tools and the commands to reproduce the whole Index from public Hugging Face
datasets: https://github.com/metermaidai/audit. The tables with every group are at
https://metermaid.ai/agent-waste-index.html.

If you run either tool with `--share` it writes share.json, an allowlisted file of aggregates with
pseudonymised ids and nothing else. Send me that and I'll reply with the three biggest fixes I can
see in it; everyone who sends gets their position against the Index back.

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
  mini-swe-agent 0.1% of runs with a >20k-char observation, OpenHands 50%, SWE-agent 55%. The
  bash-only scaffold's runs are shorter and cheaper, and it resolves 30% against SWE-agent's 53%
  on that version, so read the pair together.
- Run length dominates. The longest quintile takes 21–72% of a group's estimated spend (median
  50%) and returns 5–294× fewer resolved tasks per dollar than the shortest.

Also a retraction: an earlier 4,000-run cut of this said runs tripping any detector resolve at
half the rate, everywhere. At 341k that's true for weak models and *reverses* on Claude 3.5
SWE-smith. Details in report/notes.md.

Repo + reproduce commands in the comments. Run either tool with `--share` on your own traffic and
post or DM the share.json it writes (aggregates and pseudonymised ids only) — I'll tell you what
to fix.

---

## 4. X thread

1/ I ran waste detectors over 341,054 public AI coding-agent runs — 11 datasets, 29 model/scaffold
groups. Short version: the loop problem is solved. The run-length problem isn't.

2/ Degenerate loops and blind retries are a 2024 weak-model artifact. swe-agent-llama-70b: 14% of
runs loop, 22% blindly re-run a failing command. Claude 3.7 Sonnet: 0.4% and 0.5%.
Qwen3-Coder-480B: under 1.3%.

3/ Total mechanical waste across the whole set — loops, blind retries, oversized tool output —
is 4% of estimated spend. It is not where your money is going.

4/ Oversized tool output is a scaffold choice, not a model trait. Same Open-SWE v1.1 traces, 3
scaffolds: >20k-char observations in 0.1% of runs (mini-swe-agent), 50% (OpenHands), 55%
(SWE-agent). The capped one runs shorter and resolves 30% vs 53%: cheaper per solve, fewer solves.

5/ Here's the money. Split each group's runs into fifths by step count. The longest fifth takes
40% of estimated spend across the set (up to 72% in a group) and returns 5–294× fewer resolved
tasks per dollar than the shortest fifth. 16 of 18 groups, same direction.

6/ A correction to my own earlier post: on 4,000 runs I said runs tripping any detector resolve at
half the rate, in every group. At 341k it only holds on weak models (0.16–0.25×) and reverses on
Claude 3.5 SWE-smith (up to 1.22×). Retracted, written up in the repo.

7/ Both tools are open: a local spend audit for your Anthropic/OpenAI org (nothing leaves your
machine) and the trajectory auditor. Run either with --share, send me the share.json it writes,
I'll send back the fixes. https://github.com/metermaidai/audit

---

## 5. Discord one-liner (LangChain, Latent Space)

Ran waste detectors over 341,054 public agent runs. Loops are a solved problem (14% of runs on
2024 Llama agents, 0.4% on Claude 3.7), mechanical waste is only 4% of spend, and the actual money
is run length — the longest fifth of runs takes 40% of estimated spend and returns up to 294×
fewer resolved tasks per dollar. Open tools + reproduce steps: https://github.com/metermaidai/audit
(tables: https://metermaid.ai/agent-waste-index.html). If you run either tool on your own traffic
with --share and DM me the share.json it writes, I'll send back the top fixes.

---

## 6. LinkedIn

The people who pay for agent runs rarely see the runs. We scored 341,054 public AI coding-agent
runs from 11 open datasets to see where the spend actually goes.

Three findings:

1. The failure modes everyone builds guards for (loops, blind retries) are a 2024 problem. On
   current frontier models they are under 1% of runs.
2. Oversized tool output, the thing that quietly doubles a run's context, is a property of the
   scaffold, not the model. Same traces, three scaffolds: 0.1% of runs vs 50% vs 55%.
3. The money is in run length. The longest fifth of runs takes about 40% of estimated spend and
   returns the fewest solved tasks per dollar in 16 of 18 groups we could score. Nobody owns that
   line item until someone measures it.

We also retracted a finding from our own earlier 4,000-run cut that did not survive the full
data. The corrections are in the repo next to the numbers.

Both tools are open source and run entirely on your own machine. Link in the first comment.

**First comment:** Repo: https://github.com/metermaidai/audit. The full tables and method:
https://metermaid.ai/agent-waste-index.html.

---

## 7. Hugging Face post

We scored 341,054 agent trajectories from 11 public datasets on this hub (SWE-smith, SWE-rebench,
Open-SWE-Traces, mini-coder-trajs, agentic-coding-trajectories and others; full list in the
repo) for loops, blind retries, oversized tool output, abandoned runs and cost by run length.
Every run is scored by the same detectors on the same estimated cost basis, capped at the first
20,000 rows per dataset/config/split.

- Loops and blind retries are a weak-model artifact: 14–22% of runs on the 2024 Llama agents,
  under 1% on Claude 3.7 Sonnet and under 1.3% on Qwen3-Coder-480B.
- Oversized tool output tracks the scaffold: Open-SWE-Traces v1.1 through mini-swe-agent,
  OpenHands and SWE-agent carries a >20k-character observation in 0.1%, 50% and 55% of runs.
- The longest fifth of runs by step count takes 40% of estimated spend and resolves at 0.15× to
  0.91× the shortest fifth's rate.

Pipeline, detectors and a `sweep` command that rebuilds the whole Index from the hub are at
https://github.com/metermaidai/audit; tables at https://metermaid.ai/agent-waste-index.html. If
you published one of these datasets and a number looks wrong for your data, open an issue; the
method notes carry a corrections list and we would rather add to it than be wrong.

---

## 8. Newsletter tip (email, the afternoon of the launch)

**Subject:** 341,054 public AI agent runs, scored for waste (open data, open tools)

Hi [name], quick tip for [newsletter]. We scored 341,054 public coding-agent trajectories from
11 Hugging Face datasets for loops, blind retries, oversized output and cost by run length. The
short version: loops are a solved problem on frontier models, oversized tool output is a
scaffold choice not a model trait, and the longest fifth of runs takes 40% of estimated spend
for the fewest solved tasks per dollar. Also includes a retraction of our own earlier finding.

Tables: https://metermaid.ai/agent-waste-index.html
Repo and reproduce steps: https://github.com/metermaidai/audit
HN thread: [link once posted]

Thanks,
Alex
