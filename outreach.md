# Outreach — the first fifty accounts

The launch post brings people to the form. This file is the other half: the fifty named accounts,
the three messages, and the funnel we track them through. Everything here obeys `supported.json`
(the tests scan this file) and the rule in the strategy: never imply knowledge of a prospect's
bill, never quote a saving we have not measured, lead with the deliverable.

The deliverable to attach or link in every message:

- Sample pilot report: https://metermaid.ai/sample-report.html
- Run the free audit (five minutes): https://metermaid.ai/run-the-audit.html
- The Index: https://metermaid.ai/agent-waste-index.html

## Who goes on the list

Fifty companies, one named person each. Qualify on what you can see from outside; the spend
band is asked in conversation, never assumed.

| Signal | What to look for |
|---|---|
| Repeatable coding-agent workflow | A product or internal tool that runs an agent on tickets, PRs, migrations, test repair, or code review at volume, not a demo |
| Accessible traces | They run or fork SWE-agent, OpenHands, mini-swe-agent, or log message lists; a blog post or repo that shows the scaffold is enough |
| Objective outcomes | Tests, merges, CI, a resolve label; anything that yields one boolean per run |
| A named engineer | A platform or AI-infra lead who could make a scaffold change in a week |
| A reason now | A public model or scaffold migration, a pricing change they wrote about, a hiring post for "agent cost" or "inference efficiency", a cost complaint on X or HN |

Sources: the authors and forkers of the four scaffolds, companies that published on agent cost or
evals this year, the people who comment substantively on the launch thread, teams the strategy's
first segment describes (AI-native software companies with a coding-agent product). Warm intro
beats cold every time; note who could introduce you before writing.

## The funnel

One row per account in a spreadsheet, these columns, updated when the state changes:

`company · person · role · source · scaffold (if known) · intro path · stage · last touch · next step · stop reason`

Stages, in order: **listed → contacted → conversation → qualified → data-ready → pilot → recurring**.
Targets from the strategy: 50 → 15 → 8 → 5 → 3 → 2. The stop reason column is the point of the
sheet: where accounts stop is what we change next (segment, export, price, or pitch).

Qualified means all of: one workflow with concentrated spend, a named engineer who can act, traces
plus provider usage they can export, outcomes or an eval set, and a reason to care now.
Data-ready means they produced usable supported data within a week of saying yes. If three of
the first five qualified accounts cannot, the strategy says narrow the segment or improve the
export path before adding anything else.

## Message 1 — cold, to the engineer or head of AI

Short, one finding they can check against their own runs, one ask. No pricing, no pilot in the
first message. Subject lines that have worked in this format name the finding, not the company.

**Subject:** the longest fifth of agent runs

Hi [first name],

We scored 341,054 public coding-agent runs from 11 open datasets and the pattern that held in
nearly every group was this: the longest fifth of runs by step count takes about 40% of estimated
spend and returns the fewest solved tasks per dollar. Loops and blind retries, the things most
teams build guards for, were under 1% of runs on current models.

[One sentence on why them: "You wrote about moving [product] onto OpenHands in [month]" / "[Repo]
runs SWE-agent on every PR" / "[Person] mentioned agent cost in the [podcast] episode".]

The tools are open source and run on your machine; nothing is sent anywhere. Five minutes:
https://metermaid.ai/run-the-audit.html. It gives you your own run-length curve and where you sit
against the public set.

If you run it and want a second pair of eyes on the output, reply with the share.json it writes
(aggregates and pseudonymised ids only) and I'll send back what I'd fix first. No charge, no
deck.

Alex
metermaid.ai

## Message 2 — warm introduction (for the introducer to forward)

Written so the introducer can forward it as-is. Two paragraphs, the deliverable up front.

**Subject:** intro: Alex (metermaid) and [first name] ([company])

[Introducer], thanks for offering to connect us. [First name], short version:

metermaid finds avoidable cost across agent workflows (oversized tool output re-sent every step,
restarts, missed caching, the wrong model on the wrong task), helps your engineers test the fixes,
and measures what changed on the same tasks. We built it on a public Index of 341,054 agent runs;
what a finished report looks like is here: https://metermaid.ai/sample-report.html.

The free audit runs locally in five minutes and never sends anything unless you choose to. If it
finds something worth testing on [workflow], we do a fixed-price four-week pilot where your team
implements up to three fixes and we measure the combined result, quality included. If it finds
nothing worth that, I'll say so and you keep the audit.

Would a 25-minute call next week work? I'd want to hear what your workflow records about
outcomes, since that decides how much the audit can tell you.

Alex

## Message 3 — reply to someone who left their email on the form

Sent by a person within one business day. It asks the two questions the audit needs and offers
the two paths. The "spend" and "workflow" fields from the form are context, not something to
repeat back.

**Subject:** your metermaid audit

Hi [first name],

Thanks for asking. Two questions and you'll have a report by the end of the week:

1. What does your agent workflow run on: SWE-agent, OpenHands, mini-swe-agent, or something that
   logs message lists? A folder of runs from the last month is what the trace audit reads.
2. What does it record about outcomes: a test result, a merge, a resolve label, nothing yet?

Two ways to do it, your choice:

- **You run it.** https://metermaid.ai/run-the-audit.html, five minutes, nothing leaves your
  machine. Reply with the share.json it writes and I'll go through it with you.
- **We set it up together.** A 25-minute screen share; you keep your keys and traces on your side
  the whole time.

Either way you get your run-length curve, the findings with evidence, and where you sit against
341,054 public runs. If there's an opportunity worth testing I'll say what a pilot would cover
and cost; if there isn't, I'll say that too.

Alex

## Follow-ups and rules

- One follow-up per message, five business days later, two lines, a different finding from the
  Index (the scaffold comparison: 0.1% vs 50% vs 55% of runs with a >20k-character tool result on
  the same tasks). Then stop.
- Every claim in a message must be on the site or in `report/notes.md`. Nothing about their bill.
  No dollar savings until a comparison has run on their data.
- If they ask for a provider, trace source or feature that is not in `supported.json`, say it is
  not supported yet and ask what they export today. Three qualified accounts asking for the same
  thing is how something gets built.
- Log every touch in the sheet the same day. The sheet, not memory, decides what happens next.
