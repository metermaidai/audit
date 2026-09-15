#!/usr/bin/env python3
"""
schema.py — the task is the unit of economics.

A run (one trajectory file, one row) is an *attempt*. The thing the customer paid for is the
*task*: every attempt at the same job, including the restarts. Cost per successful task counts
all of them in the numerator. These records are what the trajectory audit writes locally
(attempts.jsonl, tasks.jsonl, optionally events.jsonl) and what the comparison harness reads.

Identity rules, in order of trust:

  task_id     an explicit field on the record (instance_id, task_id, problem_id, issue_id, or
              the field named with --task-id-field); else the file stem. Never inferred from
              text similarity: two runs are the same task because the data says so, not
              because their prompts look alike.
  attempt_id  an explicit field (attempt_id, run_id, sample_id, trajectory_id, or
              --attempt-id-field); else the file path (plus line number for .jsonl).
  order       an explicit attempt index or timestamp field; else the path order.

Outcomes are success / failure / unknown with the field they came from. Missing is unknown,
never failure. Every record says where its cost and its outcome came from.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict

SCHEMA_VERSION = 1

TASK_ID_FIELDS = ("task_id", "instance_id", "problem_id", "issue_id")
ATTEMPT_ID_FIELDS = ("attempt_id", "run_id", "sample_id", "trajectory_id", "traj_id")
ATTEMPT_ORDER_FIELDS = ("attempt", "attempt_index", "attempt_idx", "sample_idx", "sample_index",
                        "timestamp", "created_at", "start_time", "started_at")
OUTCOME_FIELDS = ("resolved", "target", "success", "verified", "passed")

SUCCESS, FAILURE, UNKNOWN = "success", "failure", "unknown"


def sha(text: str, n: int = 12) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:n]


def explicit(obj: dict, fields: tuple[str, ...], override: str | None = None):
    """The first present, non-empty field; the override wins when given. Returns (value, field)."""
    keys = (override,) + fields if override else fields
    for k in keys:
        if not k:
            continue
        v = obj.get(k)
        if v is None or v == "" or v == "None":
            continue
        return v, k
    return None, None


def outcome_of(obj: dict) -> tuple[str, str | None]:
    """(success|failure|unknown, source field). Only booleans and 0/1 count; anything else is unknown."""
    for k in OUTCOME_FIELDS:
        v = obj.get(k)
        if isinstance(v, bool):
            return (SUCCESS if v else FAILURE), k
        if isinstance(v, (int, float)) and not isinstance(v, bool) and v in (0, 1):
            return (SUCCESS if v else FAILURE), k
    return UNKNOWN, None


@dataclass
class Event:
    """One step of an attempt: the action and the shape of what came back. Local only.
    The observation itself is not stored, only its size and hash, so an events file can sit
    on disk without holding every tool output twice."""
    event_id: str
    parent_id: str          # attempt_id
    index: int
    action: str
    action_sha: str
    obs_chars: int
    obs_sha: str
    error: bool


@dataclass
class Attempt:
    attempt_id: str
    task_id: str
    workflow: str           # the submission label
    attempt_index: int      # 1-based position within the task
    retry_of: str | None    # previous attempt_id in the same task, if any
    source_format: str
    path: str
    task_id_source: str     # field name, or "filename"
    attempt_id_source: str  # field name, or "path"
    steps: int
    cost: float
    cost_source: str        # reported | tokens | chars
    tokens_in: int | None
    tokens_out: int | None
    outcome: str            # success | failure | unknown
    outcome_source: str | None
    exit_status: str | None
    repeated_prefix_steps: int = 0   # leading actions identical to the previous attempt's: work redone
    loop_steps: int = 0
    retry_steps: int = 0
    bloat_obs: int = 0


@dataclass
class Task:
    task_id: str
    workflow: str
    attempts: list[str] = field(default_factory=list)
    attempts_n: int = 0
    total_cost: float = 0.0
    first_attempt_cost: float = 0.0
    restart_cost: float = 0.0        # cost of every attempt after the first
    redone_steps: int = 0            # sum of repeated_prefix_steps over attempts 2..n
    outcome: str = UNKNOWN           # success if any attempt succeeded; failure if all failed; else unknown
    outcome_source: str | None = None


def build_tasks(attempts: list[Attempt]) -> list[Task]:
    """Group attempts into tasks. Attempts must already be ordered and indexed within their task."""
    by_task: dict[tuple[str, str], Task] = {}
    outcomes: dict[tuple[str, str], list[str]] = {}
    for a in attempts:
        key = (a.workflow, a.task_id)
        t = by_task.setdefault(key, Task(a.task_id, a.workflow))
        t.attempts.append(a.attempt_id)
        t.attempts_n += 1
        t.total_cost += a.cost
        if a.attempt_index == 1:
            t.first_attempt_cost += a.cost
        else:
            t.restart_cost += a.cost
            t.redone_steps += a.repeated_prefix_steps
        outcomes.setdefault(key, []).append(a.outcome)
        if a.outcome_source and not t.outcome_source:
            t.outcome_source = a.outcome_source
    for key, t in by_task.items():
        o = outcomes[key]
        if SUCCESS in o:
            t.outcome = SUCCESS
        elif o and all(x == FAILURE for x in o):
            t.outcome = FAILURE
        else:
            t.outcome = UNKNOWN
    return list(by_task.values())


def task_summary(tasks: list[Task]) -> dict:
    """The task-level numbers a report quotes. cost_per_successful_task counts every attempt
    of every task in the numerator and is None, not zero, when nothing succeeded."""
    n = len(tasks)
    succ = sum(1 for t in tasks if t.outcome == SUCCESS)
    fail = sum(1 for t in tasks if t.outcome == FAILURE)
    unk = n - succ - fail
    total = sum(t.total_cost for t in tasks)
    restarted = [t for t in tasks if t.attempts_n > 1]
    restart_cost = sum(t.restart_cost for t in tasks)
    if succ:
        cps, basis = total / succ, "all attempts of all tasks, divided by tasks with a successful attempt"
    elif n and unk == n:
        cps, basis = None, "undefined: no task carries an outcome"
    else:
        cps, basis = None, "undefined: no task succeeded"
    return {
        "tasks": n,
        "attempts": sum(t.attempts_n for t in tasks),
        "tasks_success": succ, "tasks_failure": fail, "tasks_unknown": unk,
        "outcome_coverage": ((succ + fail) / n) if n else None,
        "total_cost": total,
        "tasks_restarted": len(restarted),
        "restart_attempts": sum(t.attempts_n - 1 for t in restarted),
        "restart_cost": restart_cost,
        "restart_cost_share": (restart_cost / total) if total else None,
        "redone_steps": sum(t.redone_steps for t in tasks),
        "cost_per_successful_task": cps,
        "cost_per_successful_task_basis": basis,
    }


def common_prefix(a: list[str], b: list[str]) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def to_row(rec) -> dict:
    return asdict(rec)
