# Agent Waste Index

341,054 runs. Estimated cost basis: chars/4 at Sonnet-class rates — quote percentages, not dollars. Mechanical waste 4% of estimated spend; 4% spent on runs that ended without a result. Mechanical waste counts loops, blind retries and context bloat; edit thrash is reported but not counted.

Method, caveats and retractions: [notes.md](notes.md).

| dataset | config/split | model | scaffold | runs | med steps | loops | blind retries | big tool output | edit thrash | ctx exhausted | ended w/o result | mech waste % | failed-run % | resolve | w/ finding | clean | w/ big output | w/o big output |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SWE-Hero-openhands-trajectories | default/train | Qwen3-Coder-480B | openhands | 20,000 | 60 | 0% | 0% | 58% | 78% | 0% | 0% | 4% | 0% | — | — | — | — | — |
| Open-SWE-Traces | v1.0/openhands | Open-SWE v1.0 (see card) | openhands | 20,000 | 54 | 1% | 1% | 35% | 66% | 0% | 0% | 1% | 0% | 44% | 44% | 43% | 45% | 43% |
| SWE-Zero-openhands-trajectories | default/train | Qwen3-Coder-480B | openhands | 20,000 | 31 | 0% | 0% | 7% | 73% | 0% | 0% | 1% | 0% | — | — | — | — | — |
| Open-SWE-Traces | v1.2/minisweagent | Open-SWE v1.2 (see card) | minisweagent | 20,000 | 47 | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | — | — | — | — | — |
| Open-SWE-Traces | v1.1/openhands | Open-SWE v1.1 (see card) | openhands | 20,000 | 77 | 0% | 0% | 50% | 75% | 0% | 0% | 2% | 0% | — | — | — | — | — |
| mini-coder-trajs-400k | default/train | qwen3-coder-30b | mini-swe-agent | 20,000 | 30 | 1% | 1% | 0% | 0% | 0% | 2% | 0% | 2% | 19% | 23% | 19% | — | 19% |
| Open-SWE-Traces | v1.1/sweagent | Open-SWE v1.1 (see card) | sweagent | 20,000 | 76 | 0% | 2% | 55% | 76% | 0% | 0% | 2% | 0% | — | — | — | — | — |
| AgentTrove | default/train | gpt-5-nano-2025-08-07 | terminus-2 | 20,000 | 5 | 6% | 5% | 0% | 0% | 0% | 33% | 3% | 65% | — | — | — | — | — |
| Open-SWE-Traces | v1.0/sweagent | Open-SWE v1.0 (see card) | sweagent | 20,000 | 67 | 4% | 1% | 54% | 75% | 0% | 0% | 10% | 0% | 48% | 45% | 52% | 45% | 52% |
| SWE-ZERO-12M-trajectories | default/train | mini-coder-1.7B | mini-swe-agent-1 | 20,000 | 15 | 1% | 1% | 0% | 0% | 0% | 97% | 0% | 98% | — | — | — | — | — |
| Open-SWE-Traces | v1.1/minisweagent | Open-SWE v1.1 (see card) | minisweagent | 20,000 | 51 | 0% | 0% | 0% | 0% | 0% | 0% | 0% | 0% | — | — | — | — | — |
| SWE-rebench-openhands-trajectories | default/train | Qwen3-Coder-480B | openhands | 20,000 | 61 | 1% | 1% | 72% | 69% | 0% | 9% | 5% | 17% | 48% | 47% | 49% | 49% | 44% |
| SWE-agent-trajectories | default/train | swe-agent-llama-70b | swe-agent | 18,582 | 17 | 14% | 22% | 1% | 1% | 28% | 32% | 23% | 77% | 16% | 5% | 24% | 4% | 16% |
| SWE-smith-trajectories | default/ticks | claude-3-7-sonnet-20250219 | swe-agent/ticks | 15,914 | 29 | 0% | 1% | 22% | 59% | 0% | 0% | 9% | 0% | 45% | 36% | 48% | 37% | 48% |
| SWE-smith-trajectories | default/xml | claude-3-7-sonnet-20250219 | swe-agent/xml | 14,485 | 29 | 0% | 1% | 21% | 59% | 0% | 0% | 8% | 0% | 43% | 34% | 46% | 34% | 46% |
| SWE-smith-trajectories | default/tool | claude-3-7-sonnet-20250219 | swe-agent/tool | 14,374 | 30 | 0% | 1% | 20% | 60% | 0% | 0% | 6% | 0% | 38% | 28% | 41% | 28% | 40% |
| OpenHands-Sampled-Trajectories | default/train.raw | gpt-4o-2024-08-06 | openhands | 5,826 | 15 | 2% | 9% | 18% | 38% | 0% | 53% | 5% | 55% | 7% | 4% | 15% | 10% | 7% |
| SWE-smith-trajectories | default/xml | claude-3-5-sonnet-20241022 | swe-agent/xml | 5,198 | 15 | 0% | 2% | 16% | 32% | 0% | 0% | 4% | 0% | 42% | 49% | 41% | 50% | 41% |
| SWE-smith-trajectories | default/tool | claude-3-5-sonnet-20241022 | swe-agent/tool | 5,098 | 14 | 0% | 4% | 16% | 31% | 0% | 0% | 4% | 0% | 41% | 48% | 39% | 50% | 39% |
| agentic-coding-trajectories | default/train | kwai-klear-swe-smith-mini | mini-swe-agent | 5,000 | 24 | 0% | 0% | 0% | 0% | 0% | 11% | 0% | 8% | — | — | — | — | — |
| agentic-coding-trajectories | default/train | swe-smith-claude-3-7-sonnet | swe-agent | 5,000 | 27 | 1% | 1% | 18% | 56% | 0% | 0% | 7% | 0% | 44% | 38% | 45% | 39% | 45% |
| agentic-coding-trajectories | default/train | nebius-swe-rebench-openhands | openhands | 5,000 | 61 | 1% | 1% | 72% | 69% | 0% | 9% | 5% | 17% | 49% | 48% | 49% | 50% | 44% |
| SWE-smith-trajectories | default/ticks | claude-3-5-sonnet-20241022 | swe-agent/ticks | 4,033 | 17 | 0% | 1% | 10% | 35% | 0% | 0% | 3% | 0% | 41% | 45% | 41% | 46% | 41% |
| SWE-agent-trajectories | default/train | swe-agent-llama-8b | swe-agent | 1,092 | 25 | 18% | 31% | 1% | 1% | 50% | 50% | 35% | 91% | 21% | 7% | 40% | 0% | 21% |
| SWE-smith-trajectories | default/tool | gpt-4o-2024-08-06 | swe-agent/tool | 528 | 19 | 1% | 2% | 3% | 55% | 0% | 0% | 2% | 0% | 33% | 30% | 33% | 47% | 33% |
| SWE-agent-trajectories | default/train | swe-agent-llama-405b | swe-agent | 325 | 17 | 9% | 26% | 0% | 2% | 45% | 45% | 38% | 94% | 34% | 11% | 56% | 0% | 34% |
| SWE-smith-trajectories | default/xml | gpt-4o-2024-08-06 | swe-agent/xml | 317 | 19 | 1% | 2% | 3% | 55% | 0% | 0% | 4% | 0% | 28% | 19% | 29% | 30% | 28% |
| OpenHands-Sampled-Trajectories | default/train.raw | claude-3-5-sonnet-20241022 | openhands | 229 | 24 | 1% | 3% | 69% | 49% | 0% | 20% | 8% | 48% | 29% | 29% | 31% | 30% | 27% |
| SWE-smith-trajectories | default/ticks | gpt-4o-2024-08-06 | swe-agent/ticks | 53 | 17 | 2% | 2% | 0% | 53% | 0% | 0% | 0% | 0% | 2% | 0% | 2% | — | 2% |

## Resolve gap controlled for run length

Within each dataset/model, runs are split into five buckets by step count. If waste only proxied for hard tasks, the flagged/clean gap would vanish inside buckets.

| dataset | model | step bucket | n | finding rate | resolve w/ finding | resolve clean | resolve w/ big output | resolve w/o big output |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| OpenHands-Sampled-Trajectories | gpt-4o-2024-08-06 | 1 | 1,166 | 95% | 0% | 0% | — | 0% |
| OpenHands-Sampled-Trajectories | gpt-4o-2024-08-06 | 2 | 1,165 | 76% | 0% | 17% | 40% | 4% |
| OpenHands-Sampled-Trajectories | gpt-4o-2024-08-06 | 3 | 1,165 | 27% | 19% | 18% | 22% | 18% |
| OpenHands-Sampled-Trajectories | gpt-4o-2024-08-06 | 4 | 1,165 | 60% | 7% | 12% | 9% | 9% |
| OpenHands-Sampled-Trajectories | gpt-4o-2024-08-06 | 5 | 1,165 | 81% | 3% | 8% | 3% | 5% |
| SWE-smith-trajectories | claude-3-5-sonnet-20241022 | 1 | 2,866 | 17% | 60% | 44% | 73% | 44% |
| SWE-smith-trajectories | claude-3-5-sonnet-20241022 | 2 | 2,866 | 16% | 61% | 44% | 65% | 44% |
| SWE-smith-trajectories | claude-3-5-sonnet-20241022 | 3 | 2,866 | 13% | 41% | 42% | 42% | 42% |
| SWE-smith-trajectories | claude-3-5-sonnet-20241022 | 4 | 2,866 | 15% | 39% | 40% | 39% | 39% |
| SWE-smith-trajectories | claude-3-5-sonnet-20241022 | 5 | 2,865 | 21% | 39% | 32% | 40% | 32% |
| SWE-smith-trajectories | claude-3-7-sonnet-20250219 | 1 | 8,955 | 11% | 50% | 65% | 50% | 65% |
| SWE-smith-trajectories | claude-3-7-sonnet-20250219 | 2 | 8,955 | 14% | 48% | 53% | 48% | 53% |
| SWE-smith-trajectories | claude-3-7-sonnet-20250219 | 3 | 8,955 | 18% | 40% | 43% | 41% | 43% |
| SWE-smith-trajectories | claude-3-7-sonnet-20250219 | 4 | 8,954 | 28% | 29% | 33% | 30% | 33% |
| SWE-smith-trajectories | claude-3-7-sonnet-20250219 | 5 | 8,954 | 37% | 21% | 21% | 22% | 21% |
| SWE-smith-trajectories | gpt-4o-2024-08-06 | 1 | 180 | 2% | 100% | 36% | 100% | 37% |
| SWE-smith-trajectories | gpt-4o-2024-08-06 | 2 | 180 | 3% | 50% | 30% | 75% | 30% |
| SWE-smith-trajectories | gpt-4o-2024-08-06 | 3 | 180 | 6% | 0% | 38% | 0% | 36% |
| SWE-smith-trajectories | gpt-4o-2024-08-06 | 4 | 179 | 13% | 26% | 29% | 38% | 28% |
| SWE-smith-trajectories | gpt-4o-2024-08-06 | 5 | 179 | 6% | 10% | 16% | — | 16% |
| SWE-agent-trajectories | swe-agent-llama-405b | 1 | 65 | 2% | 0% | 52% | — | 51% |
| SWE-agent-trajectories | swe-agent-llama-405b | 2 | 65 | 3% | 50% | 62% | — | 62% |
| SWE-agent-trajectories | swe-agent-llama-405b | 3 | 65 | 37% | 25% | 54% | 0% | 44% |
| SWE-agent-trajectories | swe-agent-llama-405b | 4 | 65 | 100% | 8% | — | — | 8% |
| SWE-agent-trajectories | swe-agent-llama-405b | 5 | 65 | 100% | 8% | — | — | 8% |
| SWE-agent-trajectories | swe-agent-llama-70b | 1 | 3,717 | 11% | 1% | 25% | 0% | 22% |
| SWE-agent-trajectories | swe-agent-llama-70b | 2 | 3,717 | 14% | 12% | 29% | 7% | 27% |
| SWE-agent-trajectories | swe-agent-llama-70b | 3 | 3,716 | 30% | 11% | 23% | 7% | 20% |
| SWE-agent-trajectories | swe-agent-llama-70b | 4 | 3,716 | 67% | 5% | 14% | 0% | 8% |
| SWE-agent-trajectories | swe-agent-llama-70b | 5 | 3,716 | 95% | 3% | 13% | 0% | 3% |
| SWE-agent-trajectories | swe-agent-llama-8b | 1 | 219 | 2% | 0% | 47% | — | 46% |
| SWE-agent-trajectories | swe-agent-llama-8b | 2 | 219 | 13% | 21% | 40% | 0% | 38% |
| SWE-agent-trajectories | swe-agent-llama-8b | 3 | 218 | 72% | 6% | 21% | 0% | 10% |
| SWE-agent-trajectories | swe-agent-llama-8b | 4 | 218 | 98% | 3% | 0% | 0% | 3% |
| SWE-agent-trajectories | swe-agent-llama-8b | 5 | 218 | 100% | 9% | — | — | 9% |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | 1 | 4,000 | 72% | 66% | 64% | 66% | 63% |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | 2 | 4,000 | 75% | 58% | 54% | 58% | 54% |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | 3 | 4,000 | 75% | 49% | 47% | 50% | 46% |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | 4 | 4,000 | 75% | 41% | 39% | 41% | 39% |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | 5 | 4,000 | 86% | 27% | 32% | 30% | 22% |
| Open-SWE-Traces | Open-SWE v1.0 (see card) | 1 | 6,232 | 38% | 58% | 60% | 58% | 60% |
| Open-SWE-Traces | Open-SWE v1.0 (see card) | 2 | 6,232 | 41% | 51% | 51% | 51% | 51% |
| Open-SWE-Traces | Open-SWE v1.0 (see card) | 3 | 6,231 | 45% | 46% | 46% | 46% | 46% |
| Open-SWE-Traces | Open-SWE v1.0 (see card) | 4 | 6,231 | 48% | 39% | 40% | 39% | 40% |
| Open-SWE-Traces | Open-SWE v1.0 (see card) | 5 | 6,231 | 54% | 33% | 33% | 33% | 33% |
| mini-coder-trajs-400k | qwen3-coder-30b | 1 | 4,000 | 4% | 32% | 30% | — | 30% |
| mini-coder-trajs-400k | qwen3-coder-30b | 2 | 4,000 | 4% | 33% | 25% | — | 25% |
| mini-coder-trajs-400k | qwen3-coder-30b | 3 | 4,000 | 4% | 22% | 18% | — | 19% |
| mini-coder-trajs-400k | qwen3-coder-30b | 4 | 4,000 | 4% | 16% | 13% | — | 13% |
| mini-coder-trajs-400k | qwen3-coder-30b | 5 | 4,000 | 4% | 10% | 9% | — | 9% |
| agentic-coding-trajectories | nebius-swe-rebench-openhands | 1 | 1,000 | 73% | 69% | 68% | 70% | 66% |
| agentic-coding-trajectories | nebius-swe-rebench-openhands | 2 | 1,000 | 74% | 58% | 57% | 58% | 56% |
| agentic-coding-trajectories | nebius-swe-rebench-openhands | 3 | 1,000 | 75% | 49% | 43% | 49% | 42% |
| agentic-coding-trajectories | nebius-swe-rebench-openhands | 4 | 1,000 | 74% | 44% | 41% | 44% | 41% |
| agentic-coding-trajectories | nebius-swe-rebench-openhands | 5 | 1,000 | 86% | 26% | 27% | 30% | 20% |
| agentic-coding-trajectories | swe-smith-claude-3-7-sonnet | 1 | 1,000 | 9% | 60% | 64% | 59% | 64% |
| agentic-coding-trajectories | swe-smith-claude-3-7-sonnet | 2 | 1,000 | 12% | 51% | 53% | 51% | 53% |
| agentic-coding-trajectories | swe-smith-claude-3-7-sonnet | 3 | 1,000 | 16% | 52% | 46% | 53% | 46% |
| agentic-coding-trajectories | swe-smith-claude-3-7-sonnet | 4 | 1,000 | 24% | 37% | 35% | 37% | 34% |
| agentic-coding-trajectories | swe-smith-claude-3-7-sonnet | 5 | 1,000 | 34% | 22% | 21% | 23% | 20% |

## Where the money goes: cost and resolve rate by run-length quintile

Runs are split into five equal-count buckets by step count within each group. Cost share is the bucket's share of the group's estimated spend; resolved/$ is resolved tasks per estimated dollar (relative within a group).

| dataset | config/split | model | quintile | steps | cost share (no cache) | cost share (cached reads) | resolve | resolved per $ |
|---|---|---|---:|---|---:|---:|---:|---:|
| SWE-ZERO-12M-trajectories | default/train | mini-coder-1.7B | 1 | 1–15 | 18% | 18% | — | — |
| SWE-ZERO-12M-trajectories | default/train | mini-coder-1.7B | 2 | 15–15 | 21% | 21% | — | — |
| SWE-ZERO-12M-trajectories | default/train | mini-coder-1.7B | 3 | 15–15 | 21% | 21% | — | — |
| SWE-ZERO-12M-trajectories | default/train | mini-coder-1.7B | 4 | 15–15 | 19% | 20% | — | — |
| SWE-ZERO-12M-trajectories | default/train | mini-coder-1.7B | 5 | 15–85 | 21% | 21% | — | — |
| OpenHands-Sampled-Trajectories | default/train.raw | gpt-4o-2024-08-06 | 1 | 3–4 | 0% | 0% | 0% | 0.00 |
| OpenHands-Sampled-Trajectories | default/train.raw | gpt-4o-2024-08-06 | 2 | 4–10 | 1% | 1% | 5% | 2.40 |
| OpenHands-Sampled-Trajectories | default/train.raw | gpt-4o-2024-08-06 | 3 | 10–19 | 8% | 12% | 18% | 0.66 |
| OpenHands-Sampled-Trajectories | default/train.raw | gpt-4o-2024-08-06 | 4 | 19–31 | 24% | 26% | 10% | 0.13 |
| OpenHands-Sampled-Trajectories | default/train.raw | gpt-4o-2024-08-06 | 5 | 31–99 | 67% | 60% | 4% | 0.02 |
| SWE-smith-trajectories | default/ticks | claude-3-5-sonnet-20241022 | 1 | 5–11 | 2% | 4% | 40% | 3.12 |
| SWE-smith-trajectories | default/ticks | claude-3-5-sonnet-20241022 | 2 | 11–14 | 4% | 7% | 45% | 1.81 |
| SWE-smith-trajectories | default/ticks | claude-3-5-sonnet-20241022 | 3 | 14–20 | 8% | 10% | 41% | 0.96 |
| SWE-smith-trajectories | default/ticks | claude-3-5-sonnet-20241022 | 4 | 20–30 | 16% | 17% | 44% | 0.51 |
| SWE-smith-trajectories | default/ticks | claude-3-5-sonnet-20241022 | 5 | 30–138 | 70% | 61% | 37% | 0.09 |
| SWE-smith-trajectories | default/ticks | claude-3-7-sonnet-20250219 | 1 | 7–20 | 5% | 6% | 66% | 1.65 |
| SWE-smith-trajectories | default/ticks | claude-3-7-sonnet-20250219 | 2 | 20–26 | 8% | 10% | 55% | 0.74 |
| SWE-smith-trajectories | default/ticks | claude-3-7-sonnet-20250219 | 3 | 26–34 | 14% | 15% | 46% | 0.39 |
| SWE-smith-trajectories | default/ticks | claude-3-7-sonnet-20250219 | 4 | 34–48 | 23% | 24% | 36% | 0.17 |
| SWE-smith-trajectories | default/ticks | claude-3-7-sonnet-20250219 | 5 | 48–151 | 50% | 44% | 23% | 0.05 |
| SWE-smith-trajectories | default/tool | claude-3-5-sonnet-20241022 | 1 | 4–10 | 2% | 5% | 50% | 4.36 |
| SWE-smith-trajectories | default/tool | claude-3-5-sonnet-20241022 | 2 | 10–12 | 4% | 7% | 47% | 2.41 |
| SWE-smith-trajectories | default/tool | claude-3-5-sonnet-20241022 | 3 | 12–17 | 7% | 10% | 40% | 1.27 |
| SWE-smith-trajectories | default/tool | claude-3-5-sonnet-20241022 | 4 | 17–26 | 14% | 17% | 37% | 0.55 |
| SWE-smith-trajectories | default/tool | claude-3-5-sonnet-20241022 | 5 | 26–127 | 72% | 62% | 31% | 0.09 |
| SWE-smith-trajectories | default/tool | claude-3-7-sonnet-20250219 | 1 | 8–20 | 4% | 6% | 59% | 1.55 |
| SWE-smith-trajectories | default/tool | claude-3-7-sonnet-20250219 | 2 | 20–26 | 8% | 10% | 47% | 0.65 |
| SWE-smith-trajectories | default/tool | claude-3-7-sonnet-20250219 | 3 | 26–34 | 13% | 15% | 37% | 0.31 |
| SWE-smith-trajectories | default/tool | claude-3-7-sonnet-20250219 | 4 | 34–48 | 24% | 24% | 28% | 0.13 |
| SWE-smith-trajectories | default/tool | claude-3-7-sonnet-20250219 | 5 | 48–151 | 51% | 45% | 19% | 0.04 |
| SWE-smith-trajectories | default/xml | claude-3-5-sonnet-20241022 | 1 | 4–10 | 2% | 5% | 48% | 4.12 |
| SWE-smith-trajectories | default/xml | claude-3-5-sonnet-20241022 | 2 | 10–13 | 4% | 7% | 50% | 2.41 |
| SWE-smith-trajectories | default/xml | claude-3-5-sonnet-20241022 | 3 | 13–18 | 7% | 10% | 42% | 1.23 |
| SWE-smith-trajectories | default/xml | claude-3-5-sonnet-20241022 | 4 | 18–27 | 15% | 17% | 40% | 0.55 |
| SWE-smith-trajectories | default/xml | claude-3-5-sonnet-20241022 | 5 | 27–127 | 72% | 61% | 31% | 0.09 |
| SWE-smith-trajectories | default/xml | claude-3-7-sonnet-20250219 | 1 | 6–19 | 4% | 6% | 65% | 1.70 |
| SWE-smith-trajectories | default/xml | claude-3-7-sonnet-20250219 | 2 | 19–26 | 8% | 10% | 53% | 0.71 |
| SWE-smith-trajectories | default/xml | claude-3-7-sonnet-20250219 | 3 | 26–34 | 14% | 15% | 44% | 0.36 |
| SWE-smith-trajectories | default/xml | claude-3-7-sonnet-20250219 | 4 | 34–48 | 24% | 24% | 33% | 0.16 |
| SWE-smith-trajectories | default/xml | claude-3-7-sonnet-20250219 | 5 | 48–151 | 50% | 44% | 21% | 0.05 |
| SWE-agent-trajectories | default/train | swe-agent-llama-70b | 1 | 1–10 | 1% | 3% | 22% | 5.20 |
| SWE-agent-trajectories | default/train | swe-agent-llama-70b | 2 | 10–14 | 3% | 6% | 27% | 2.80 |
| SWE-agent-trajectories | default/train | swe-agent-llama-70b | 3 | 14–21 | 7% | 11% | 19% | 0.87 |
| SWE-agent-trajectories | default/train | swe-agent-llama-70b | 4 | 21–37 | 23% | 26% | 8% | 0.12 |
| SWE-agent-trajectories | default/train | swe-agent-llama-70b | 5 | 37–398 | 64% | 55% | 3% | 0.02 |
| SWE-agent-trajectories | default/train | swe-agent-llama-8b | 1 | 3–11 | 1% | 2% | 46% | 10.07 |
| SWE-agent-trajectories | default/train | swe-agent-llama-8b | 2 | 11–18 | 3% | 5% | 37% | 3.10 |
| SWE-agent-trajectories | default/train | swe-agent-llama-8b | 3 | 18–33 | 14% | 17% | 10% | 0.16 |
| SWE-agent-trajectories | default/train | swe-agent-llama-8b | 4 | 33–47 | 28% | 29% | 3% | 0.02 |
| SWE-agent-trajectories | default/train | swe-agent-llama-8b | 5 | 47–321 | 55% | 47% | 9% | 0.04 |
| SWE-rebench-openhands-trajectories | default/train | Qwen3-Coder-480B | 1 | 21–48 | 10% | 11% | 65% | 0.26 |
| SWE-rebench-openhands-trajectories | default/train | Qwen3-Coder-480B | 2 | 48–56 | 14% | 15% | 57% | 0.16 |
| SWE-rebench-openhands-trajectories | default/train | Qwen3-Coder-480B | 3 | 56–66 | 18% | 18% | 49% | 0.11 |
| SWE-rebench-openhands-trajectories | default/train | Qwen3-Coder-480B | 4 | 66–81 | 24% | 23% | 41% | 0.07 |
| SWE-rebench-openhands-trajectories | default/train | Qwen3-Coder-480B | 5 | 81–114 | 35% | 32% | 27% | 0.03 |
| Open-SWE-Traces | v1.0/openhands | Open-SWE v1.0 (see card) | 1 | 11–39 | 7% | 9% | 57% | 0.31 |
| Open-SWE-Traces | v1.0/openhands | Open-SWE v1.0 (see card) | 2 | 39–49 | 12% | 13% | 49% | 0.15 |
| Open-SWE-Traces | v1.0/openhands | Open-SWE v1.0 (see card) | 3 | 49–60 | 16% | 17% | 43% | 0.10 |
| Open-SWE-Traces | v1.0/openhands | Open-SWE v1.0 (see card) | 4 | 60–75 | 23% | 23% | 37% | 0.05 |
| Open-SWE-Traces | v1.0/openhands | Open-SWE v1.0 (see card) | 5 | 75–200 | 42% | 39% | 30% | 0.02 |
| Open-SWE-Traces | v1.0/sweagent | Open-SWE v1.0 (see card) | 1 | 8–47 | 6% | 7% | 64% | 0.27 |
| Open-SWE-Traces | v1.0/sweagent | Open-SWE v1.0 (see card) | 2 | 47–60 | 11% | 12% | 53% | 0.12 |
| Open-SWE-Traces | v1.0/sweagent | Open-SWE v1.0 (see card) | 3 | 60–75 | 16% | 17% | 46% | 0.06 |
| Open-SWE-Traces | v1.0/sweagent | Open-SWE v1.0 (see card) | 4 | 75–95 | 24% | 23% | 41% | 0.04 |
| Open-SWE-Traces | v1.0/sweagent | Open-SWE v1.0 (see card) | 5 | 95–200 | 43% | 40% | 33% | 0.02 |
| Open-SWE-Traces | v1.1/minisweagent | Open-SWE v1.1 (see card) | 1 | 10–38 | 7% | 9% | — | — |
| Open-SWE-Traces | v1.1/minisweagent | Open-SWE v1.1 (see card) | 2 | 38–47 | 12% | 14% | — | — |
| Open-SWE-Traces | v1.1/minisweagent | Open-SWE v1.1 (see card) | 3 | 47–56 | 16% | 18% | — | — |
| Open-SWE-Traces | v1.1/minisweagent | Open-SWE v1.1 (see card) | 4 | 56–71 | 22% | 22% | — | — |
| Open-SWE-Traces | v1.1/minisweagent | Open-SWE v1.1 (see card) | 5 | 71–250 | 43% | 37% | — | — |
| Open-SWE-Traces | v1.1/openhands | Open-SWE v1.1 (see card) | 1 | 17–64 | 13% | 14% | — | — |
| Open-SWE-Traces | v1.1/openhands | Open-SWE v1.1 (see card) | 2 | 64–72 | 16% | 17% | — | — |
| Open-SWE-Traces | v1.1/openhands | Open-SWE v1.1 (see card) | 3 | 72–81 | 19% | 19% | — | — |
| Open-SWE-Traces | v1.1/openhands | Open-SWE v1.1 (see card) | 4 | 81–94 | 22% | 21% | — | — |
| Open-SWE-Traces | v1.1/openhands | Open-SWE v1.1 (see card) | 5 | 94–246 | 31% | 28% | — | — |
| Open-SWE-Traces | v1.1/sweagent | Open-SWE v1.1 (see card) | 1 | 19–63 | 11% | 13% | — | — |
| Open-SWE-Traces | v1.1/sweagent | Open-SWE v1.1 (see card) | 2 | 63–72 | 15% | 16% | — | — |
| Open-SWE-Traces | v1.1/sweagent | Open-SWE v1.1 (see card) | 3 | 72–81 | 18% | 19% | — | — |
| Open-SWE-Traces | v1.1/sweagent | Open-SWE v1.1 (see card) | 4 | 81–95 | 22% | 22% | — | — |
| Open-SWE-Traces | v1.1/sweagent | Open-SWE v1.1 (see card) | 5 | 95–245 | 33% | 30% | — | — |
| Open-SWE-Traces | v1.2/minisweagent | Open-SWE v1.2 (see card) | 1 | 10–32 | 3% | 5% | — | — |
| Open-SWE-Traces | v1.2/minisweagent | Open-SWE v1.2 (see card) | 2 | 32–42 | 7% | 9% | — | — |
| Open-SWE-Traces | v1.2/minisweagent | Open-SWE v1.2 (see card) | 3 | 42–54 | 11% | 13% | — | — |
| Open-SWE-Traces | v1.2/minisweagent | Open-SWE v1.2 (see card) | 4 | 54–75 | 20% | 21% | — | — |
| Open-SWE-Traces | v1.2/minisweagent | Open-SWE v1.2 (see card) | 5 | 75–274 | 59% | 53% | — | — |
| SWE-Hero-openhands-trajectories | default/train | Qwen3-Coder-480B | 1 | 25–48 | 11% | 13% | — | — |
| SWE-Hero-openhands-trajectories | default/train | Qwen3-Coder-480B | 2 | 48–56 | 15% | 16% | — | — |
| SWE-Hero-openhands-trajectories | default/train | Qwen3-Coder-480B | 3 | 56–64 | 18% | 19% | — | — |
| SWE-Hero-openhands-trajectories | default/train | Qwen3-Coder-480B | 4 | 64–76 | 23% | 23% | — | — |
| SWE-Hero-openhands-trajectories | default/train | Qwen3-Coder-480B | 5 | 76–100 | 33% | 30% | — | — |
| SWE-Zero-openhands-trajectories | default/train | Qwen3-Coder-480B | 1 | 10–22 | 7% | 9% | — | — |
| SWE-Zero-openhands-trajectories | default/train | Qwen3-Coder-480B | 2 | 22–28 | 11% | 13% | — | — |
| SWE-Zero-openhands-trajectories | default/train | Qwen3-Coder-480B | 3 | 28–34 | 16% | 17% | — | — |
| SWE-Zero-openhands-trajectories | default/train | Qwen3-Coder-480B | 4 | 34–43 | 24% | 23% | — | — |
| SWE-Zero-openhands-trajectories | default/train | Qwen3-Coder-480B | 5 | 43–100 | 43% | 37% | — | — |
| AgentTrove | default/train | gpt-5-nano-2025-08-07 | 1 | 1–2 | 4% | 6% | — | — |
| AgentTrove | default/train | gpt-5-nano-2025-08-07 | 2 | 2–4 | 5% | 7% | — | — |
| AgentTrove | default/train | gpt-5-nano-2025-08-07 | 3 | 4–7 | 15% | 16% | — | — |
| AgentTrove | default/train | gpt-5-nano-2025-08-07 | 4 | 7–8 | 38% | 35% | — | — |
| AgentTrove | default/train | gpt-5-nano-2025-08-07 | 5 | 8–8 | 39% | 36% | — | — |
| mini-coder-trajs-400k | default/train | qwen3-coder-30b | 1 | 3–19 | 4% | 6% | 30% | 2.06 |
| mini-coder-trajs-400k | default/train | qwen3-coder-30b | 2 | 19–26 | 8% | 11% | 25% | 0.86 |
| mini-coder-trajs-400k | default/train | qwen3-coder-30b | 3 | 26–34 | 14% | 16% | 18% | 0.37 |
| mini-coder-trajs-400k | default/train | qwen3-coder-30b | 4 | 34–48 | 23% | 24% | 14% | 0.16 |
| mini-coder-trajs-400k | default/train | qwen3-coder-30b | 5 | 48–256 | 51% | 44% | 9% | 0.05 |
| agentic-coding-trajectories | default/train | kwai-klear-swe-smith-mini | 1 | 9–17 | 5% | 8% | — | — |
| agentic-coding-trajectories | default/train | kwai-klear-swe-smith-mini | 2 | 17–22 | 9% | 12% | — | — |
| agentic-coding-trajectories | default/train | kwai-klear-swe-smith-mini | 3 | 22–27 | 14% | 16% | — | — |
| agentic-coding-trajectories | default/train | kwai-klear-swe-smith-mini | 4 | 27–36 | 22% | 23% | — | — |
| agentic-coding-trajectories | default/train | kwai-klear-swe-smith-mini | 5 | 36–83 | 49% | 41% | — | — |
| agentic-coding-trajectories | default/train | nebius-swe-rebench-openhands | 1 | 26–48 | 10% | 12% | 68% | 0.27 |
| agentic-coding-trajectories | default/train | nebius-swe-rebench-openhands | 2 | 48–56 | 14% | 15% | 58% | 0.17 |
| agentic-coding-trajectories | default/train | nebius-swe-rebench-openhands | 3 | 56–66 | 18% | 18% | 47% | 0.11 |
| agentic-coding-trajectories | default/train | nebius-swe-rebench-openhands | 4 | 66–81 | 23% | 23% | 44% | 0.07 |
| agentic-coding-trajectories | default/train | nebius-swe-rebench-openhands | 5 | 81–100 | 35% | 32% | 26% | 0.03 |
| agentic-coding-trajectories | default/train | swe-smith-claude-3-7-sonnet | 1 | 3–18 | 4% | 6% | 63% | 1.91 |
| agentic-coding-trajectories | default/train | swe-smith-claude-3-7-sonnet | 2 | 18–24 | 8% | 10% | 54% | 0.87 |
| agentic-coding-trajectories | default/train | swe-smith-claude-3-7-sonnet | 3 | 24–31 | 13% | 15% | 47% | 0.45 |
| agentic-coding-trajectories | default/train | swe-smith-claude-3-7-sonnet | 4 | 31–45 | 22% | 23% | 34% | 0.19 |
| agentic-coding-trajectories | default/train | swe-smith-claude-3-7-sonnet | 5 | 45–120 | 52% | 46% | 21% | 0.05 |

## How runs ended (sanity check on end-of-run classification)

| dataset | model | terminal | exit_status | n |
|---|---|---|---|---:|
| SWE-ZERO-12M-trajectories | mini-coder-1.7B | incomplete | incomplete | 19,351 |
| SWE-ZERO-12M-trajectories | mini-coder-1.7B | submitted | Submitted | 649 |
| OpenHands-Sampled-Trajectories | claude-3-5-sonnet-20241022 | submitted |  | 182 |
| OpenHands-Sampled-Trajectories | claude-3-5-sonnet-20241022 | cutoff |  | 45 |
| OpenHands-Sampled-Trajectories | claude-3-5-sonnet-20241022 | text_end |  | 2 |
| OpenHands-Sampled-Trajectories | gpt-4o-2024-08-06 | cutoff |  | 3,100 |
| OpenHands-Sampled-Trajectories | gpt-4o-2024-08-06 | submitted |  | 2,572 |
| OpenHands-Sampled-Trajectories | gpt-4o-2024-08-06 | text_end |  | 154 |
| SWE-smith-trajectories | claude-3-5-sonnet-20241022 | submitted |  | 13,492 |
| SWE-smith-trajectories | claude-3-5-sonnet-20241022 | text_end |  | 837 |
| SWE-smith-trajectories | claude-3-7-sonnet-20250219 | submitted |  | 43,201 |
| SWE-smith-trajectories | claude-3-7-sonnet-20250219 | text_end |  | 1,572 |
| SWE-smith-trajectories | gpt-4o-2024-08-06 | submitted |  | 764 |
| SWE-smith-trajectories | gpt-4o-2024-08-06 | text_end |  | 134 |
| SWE-agent-trajectories | swe-agent-llama-405b | submitted | submitted | 170 |
| SWE-agent-trajectories | swe-agent-llama-405b | context_exhausted | submitted (exit_context) | 135 |
| SWE-agent-trajectories | swe-agent-llama-405b | context_exhausted | exit_context | 10 |
| SWE-agent-trajectories | swe-agent-llama-405b | submitted | submitted_no_patch | 9 |
| SWE-agent-trajectories | swe-agent-llama-405b | cutoff | submitted (exit_format) | 1 |
| SWE-agent-trajectories | swe-agent-llama-70b | submitted | submitted | 12,344 |
| SWE-agent-trajectories | swe-agent-llama-70b | context_exhausted | submitted (exit_context) | 4,402 |
| SWE-agent-trajectories | swe-agent-llama-70b | context_exhausted | exit_context | 839 |
| SWE-agent-trajectories | swe-agent-llama-70b | cutoff | early_exit | 698 |
| SWE-agent-trajectories | swe-agent-llama-70b | submitted | submitted_no_patch | 266 |
| SWE-agent-trajectories | swe-agent-llama-70b | cutoff | submitted (exit_format) | 17 |
| SWE-agent-trajectories | swe-agent-llama-70b | cutoff | exit_format | 7 |
| SWE-agent-trajectories | swe-agent-llama-70b | submitted | early_exit | 5 |
| SWE-agent-trajectories | swe-agent-llama-70b | incomplete | submitted (exit_cost) | 3 |
| SWE-agent-trajectories | swe-agent-llama-70b | incomplete | exit_cost | 1 |
| SWE-agent-trajectories | swe-agent-llama-8b | submitted | submitted | 535 |
| SWE-agent-trajectories | swe-agent-llama-8b | context_exhausted | submitted (exit_context) | 516 |
| SWE-agent-trajectories | swe-agent-llama-8b | context_exhausted | exit_context | 33 |
| SWE-agent-trajectories | swe-agent-llama-8b | submitted | submitted_no_patch | 7 |
| SWE-agent-trajectories | swe-agent-llama-8b | cutoff | early_exit | 1 |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | submitted | submit | 18,106 |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | incomplete | RuntimeError: Agent reached maximum iter | 1,800 |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | incomplete | AgentStuckInLoopError: Agent got stuck i | 69 |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | incomplete | Timeout: litellm.Timeout: APITimeoutErro | 13 |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | incomplete | RuntimeError: There was an unexpected er | 7 |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | submitted | unknown | 4 |
| SWE-rebench-openhands-trajectories | Qwen3-Coder-480B | incomplete | AttributeError: 'str' object has no attr | 1 |
| Open-SWE-Traces | Open-SWE v1.0 (see card) | submitted |  | 39,999 |
| Open-SWE-Traces | Open-SWE v1.0 (see card) | cutoff |  | 1 |
| Open-SWE-Traces | Open-SWE v1.1 (see card) | submitted |  | 59,997 |
| Open-SWE-Traces | Open-SWE v1.1 (see card) | cutoff |  | 3 |
| Open-SWE-Traces | Open-SWE v1.2 (see card) | submitted |  | 20,000 |
| SWE-Hero-openhands-trajectories | Qwen3-Coder-480B | submitted |  | 20,000 |
| SWE-Zero-openhands-trajectories | Qwen3-Coder-480B | submitted |  | 20,000 |
| AgentTrove | gpt-5-nano-2025-08-07 | submitted |  | 13,109 |
| AgentTrove | gpt-5-nano-2025-08-07 | cutoff |  | 6,598 |
| AgentTrove | gpt-5-nano-2025-08-07 | text_end |  | 293 |
| mini-coder-trajs-400k | qwen3-coder-30b | submitted |  | 19,512 |
| mini-coder-trajs-400k | qwen3-coder-30b | cutoff |  | 480 |
| mini-coder-trajs-400k | qwen3-coder-30b | text_end |  | 8 |
| agentic-coding-trajectories | kwai-klear-swe-smith-mini | submitted |  | 4,472 |
| agentic-coding-trajectories | kwai-klear-swe-smith-mini | cutoff |  | 528 |
| agentic-coding-trajectories | nebius-swe-rebench-openhands | submitted |  | 4,527 |
| agentic-coding-trajectories | nebius-swe-rebench-openhands | cutoff |  | 471 |
| agentic-coding-trajectories | nebius-swe-rebench-openhands | text_end |  | 2 |
| agentic-coding-trajectories | swe-smith-claude-3-7-sonnet | submitted |  | 4,620 |
| agentic-coding-trajectories | swe-smith-claude-3-7-sonnet | text_end |  | 380 |