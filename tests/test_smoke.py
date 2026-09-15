#!/usr/bin/env python3
"""
Smoke and regression tests. Standard library only; the parts that need duckdb or
pyarrow skip themselves when those are absent.

    python tests/test_smoke.py            # or: python -m unittest discover tests

Every test here corresponds to a defect that actually shipped. Adding a detector,
changing what counts as mechanical waste, or editing a headline number in the docs
should either keep these passing or be accompanied by a deliberate change to them.
"""
from __future__ import annotations
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["metermaid_audit.py", "trajectory_audit.py", "pipeline.py", "benchmark.py",
           "hf_pull.py", "hf_batch.py", "download_logs.py", "share.py", "schema.py"]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def have(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


def run_traj(tmp: Path, runs: dict[str, dict]) -> dict:
    """Write each run as its own JSON file, audit the directory, return the JSON report."""
    src = tmp / "traj" / "sub"
    src.mkdir(parents=True)
    for name, doc in runs.items():
        (src / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    out = tmp / "out"
    subprocess.run([sys.executable, str(ROOT / "trajectory_audit.py"), str(tmp / "traj"),
                    "--out", str(out)], check=True, capture_output=True)
    return json.loads((out / "trajectory-audit.json").read_text(encoding="utf-8"))


def submit_run(**extra) -> dict:
    msgs = [{"role": "assistant", "content": "open foo.py"}, {"role": "user", "content": "ok"},
            {"role": "assistant", "content": "submit"}, {"role": "user", "content": "done"}]
    return {"messages": msgs, **extra}


class TestScriptsLoad(unittest.TestCase):
    def test_all_scripts_compile(self):
        r = subprocess.run([sys.executable, "-m", "py_compile", *[str(ROOT / s) for s in SCRIPTS]],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_clis_show_help(self):
        for script in ("metermaid_audit.py", "trajectory_audit.py", "pipeline.py"):
            with self.subTest(script=script):
                r = subprocess.run([sys.executable, str(ROOT / script), "--help"],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)


class TestSpendAudit(unittest.TestCase):
    def test_demo_writes_a_report(self):
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run([sys.executable, str(ROOT / "metermaid_audit.py"), "--demo",
                                "--days", "30", "--out", td], capture_output=True, text=True, cwd=td)
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads((Path(td) / "audit.json").read_text(encoding="utf-8"))
            self.assertTrue((Path(td) / "audit.md").exists())
            self.assertTrue(data["result"]["findings"], "demo run produced no findings")

    def test_keyless_paths_work_without_requests(self):
        """--help and --demo do no network I/O, and the README offers --demo to people
        with no keys, so neither may require requests to be installed."""
        with tempfile.TemporaryDirectory() as block, tempfile.TemporaryDirectory() as td:
            (Path(block) / "requests.py").write_text('raise ImportError("blocked for test")',
                                                     encoding="utf-8")
            env = {**os.environ, "PYTHONPATH": block}
            for args in (["--help"], ["--demo", "--days", "30", "--out", td]):
                with self.subTest(args=args[0]):
                    r = subprocess.run([sys.executable, str(ROOT / "metermaid_audit.py"), *args],
                                       capture_output=True, text=True, env=env, cwd=td)
                    self.assertEqual(r.returncode, 0, r.stderr)

    def test_anon_strips_identifiers(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([sys.executable, str(ROOT / "metermaid_audit.py"), "--demo",
                            "--days", "30", "--anon", "--out", td],
                           check=True, capture_output=True, cwd=td)
            blob = (Path(td) / "audit.json").read_text(encoding="utf-8")
            for secret in ("sk-ant-", "sk-admin", "@"):
                self.assertNotIn(secret, blob, f"--anon leaked {secret!r}")


class TestRateCard(unittest.TestCase):
    """The rate card is where every dollar in the spend audit comes from. It once priced
    Claude Opus 5 and Sonnet 5 at the previous generation's rates (3x and 1.5x too high),
    with nothing in the file or the report saying when any price had last been checked."""

    def setUp(self):
        self.card = json.loads((ROOT / "ratecard.json").read_text(encoding="utf-8"))

    def test_card_is_versioned_and_every_row_says_when_it_was_verified(self):
        self.assertRegex(self.card["price_version"], r"^\d{4}-\d{2}-\d{2}$")
        for name, row in self.card["models"].items():
            with self.subTest(model=name):
                self.assertIn("verified_on", row, "row has no verified_on field")
                if row["verified_on"] is not None:
                    self.assertRegex(row["verified_on"], r"^\d{4}-\d{2}-\d{2}$")
                for k in ("tier", "input", "output", "cache_read", "cache_write"):
                    self.assertIn(k, row)

    def test_current_claude_generation_is_not_priced_at_the_previous_one(self):
        m = self.card["models"]
        self.assertEqual((m["claude-opus-5"]["input"], m["claude-opus-5"]["output"]), (5.0, 25.0))
        self.assertEqual((m["claude-sonnet-5"]["input"], m["claude-sonnet-5"]["output"]), (2.0, 10.0))
        # the generic claude-opus-4 row is for 4 and 4.1; 4.5+ must resolve to their own rows
        audit = load("metermaid_audit")
        rc = audit.RateCard(ROOT / "ratecard.json")
        self.assertEqual(rc.lookup("claude-opus-4-1-20250805")["input"], 15.0)
        self.assertEqual(rc.lookup("claude-opus-4-6")["input"], 5.0)
        self.assertEqual(rc.lookup("claude-sonnet-5")["input"], 2.0)

    def test_report_names_the_price_version_and_lists_stale_prices(self):
        """A card whose rows were verified long ago (or never) must say so in the report,
        on stderr, and in the JSON, but must not stop the audit from running."""
        with tempfile.TemporaryDirectory() as td:
            card = json.loads((ROOT / "ratecard.json").read_text(encoding="utf-8"))
            card["price_version"] = "2020-01-01"
            for row in card["models"].values():
                row["verified_on"] = "2020-01-01"
            card["models"]["gpt-5"]["verified_on"] = None
            rc_path = Path(td) / "old.json"
            rc_path.write_text(json.dumps(card), encoding="utf-8")
            r = subprocess.run([sys.executable, str(ROOT / "metermaid_audit.py"), "--demo", "--days", "30",
                                "--out", td, "--ratecard", str(rc_path)], capture_output=True, text=True, cwd=td)
            self.assertEqual(r.returncode, 0, r.stderr)
            md = (Path(td) / "audit.md").read_text(encoding="utf-8")
            data = json.loads((Path(td) / "audit.json").read_text(encoding="utf-8"))["result"]
            self.assertIn("rate card 2020-01-01", md)
            self.assertIn("unverified or stale", md)
            self.assertIn("gpt-5: never verified", md)
            self.assertIn("older than 90 days", r.stderr)
            stale = {s["model"]: s for s in data["stale_prices"]}
            self.assertIsNone(stale["gpt-5"]["verified_on"])
            self.assertGreater(stale["gpt-4o"]["age_days"], 90)
            # only models the run actually priced are listed; the demo never touches o3
            self.assertNotIn("o3", stale)

    def test_fresh_prices_produce_no_stale_section(self):
        audit = load("metermaid_audit")
        from datetime import datetime, timezone
        rc = audit.RateCard(ROOT / "ratecard.json", today=datetime(2026, 9, 15, tzinfo=timezone.utc))
        rc.lookup("claude-opus-5")
        self.assertEqual(rc.stale(), [])


class TestShareExport(unittest.TestCase):
    """share.json is the one file meant to leave the machine. It is built by allowlist, so
    these tests check what it must carry and, more importantly, what it must not."""

    TRAJ_KEYS = {"schema_version", "tool", "generated_at", "omitted", "trajectories", "total_cost",
                 "waste_cost", "waste_share", "sunk_cost", "sunk_share", "curve", "submissions"}
    SPEND_KEYS = {"schema_version", "tool", "generated_at", "omitted", "window_days", "price_version",
                  "estimated_spend_monthly", "provider_reported_cost_window", "by_provider_monthly",
                  "by_model_monthly", "unowned_share", "frontier_share_of_spend", "opportunity",
                  "findings", "top_keys_monthly", "unknown_models", "stale_prices"}

    @staticmethod
    def _run_with_commands() -> dict:
        """Three turns of the same two tool calls, both erroring, the second with an
        oversized payload, then a submit. Its actions carry commands the share must not."""
        msgs = []
        for i in range(3):
            msgs.append({"role": "assistant", "content": "", "tool_calls": [
                {"id": f"a{i}", "type": "function", "function": {"name": "bash", "arguments": "{\"cmd\": \"pytest tests/a.py\"}"}},
                {"id": f"b{i}", "type": "function", "function": {"name": "bash", "arguments": "{\"cmd\": \"pytest tests/b.py\"}"}}]})
            msgs.append({"role": "tool", "tool_call_id": f"a{i}", "content": "Error: boom A"})
            msgs.append({"role": "tool", "tool_call_id": f"b{i}", "content": "Error: boom B " + "x" * 30_000})
        msgs += [{"role": "assistant", "content": "submit"}, {"role": "user", "content": "done"}]
        return {"messages": msgs}

    @staticmethod
    def _keys(obj, found=None) -> set:
        """Every dict key anywhere in a payload."""
        found = set() if found is None else found
        if isinstance(obj, dict):
            for k, v in obj.items():
                found.add(k)
                TestShareExport._keys(v, found)
        elif isinstance(obj, list):
            for v in obj:
                TestShareExport._keys(v, found)
        return found

    def _traj_share(self, td: Path, salt: str | None = None) -> tuple[dict, str, dict]:
        """Audit a directory holding one run whose file name is the kind of repo__issue id
        real traces use, with --share."""
        src = td / "acme-traces" / "sub"
        src.mkdir(parents=True)
        (src / "acme__issue-42.json").write_text(json.dumps(self._run_with_commands()), encoding="utf-8")
        out = td / "out"
        args = [sys.executable, str(ROOT / "trajectory_audit.py"), str(td / "acme-traces"), "--out", str(out), "--share"]
        if salt:
            args += ["--salt", salt]
        r = subprocess.run(args, capture_output=True, text=True, check=True, cwd=td)
        return (json.loads((out / "share.json").read_text(encoding="utf-8")), r.stdout,
                json.loads((out / "trajectory-audit.json").read_text(encoding="utf-8")))

    @staticmethod
    def _blob(payload: dict) -> str:
        """The payload as text, minus the omitted-list prose (which names the very things
        the leak checks look for)."""
        return json.dumps({k: v for k, v in payload.items() if k != "omitted"})

    def test_trajectory_share_is_allowlisted_and_carries_no_run_ids_or_commands(self):
        with tempfile.TemporaryDirectory() as td:
            payload, stdout, local = self._traj_share(Path(td))
        self.assertEqual(set(payload), self.TRAJ_KEYS)
        blob = self._blob(payload)
        local_blob = json.dumps(local)
        # the run id, submission label and commands all appear in the local report...
        for leak in ("acme__issue-42", "acme-traces", "pytest tests/a.py"):
            self.assertIn(leak, local_blob, f"fixture no longer exercises {leak!r}")
            # ...and none of them in the share file
            self.assertNotIn(leak, blob, f"share.json leaked {leak!r}")
        self.assertFalse(self._keys(payload) & {"traj_id", "note", "submission", "idx", "unparsed"})
        self.assertEqual(payload["trajectories"], local["trajectories"])
        sub = next(iter(payload["submissions"].values()))
        self.assertIn("T01 tool loop", sub["by_detector"])
        self.assertTrue(sub["worst"])
        self.assertTrue(all(set(w) == {"detector", "wasted_steps", "wasted_cost"} for w in sub["worst"]))
        self.assertIn("share.json", stdout)
        self.assertIn("never contains", stdout)
        self.assertEqual(payload["omitted"], load("share").OMITTED)

    def test_fixed_salt_gives_comparable_ids_and_random_salt_does_not(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b, tempfile.TemporaryDirectory() as c:
            ida = sorted(self._traj_share(Path(a), "pepper")[0]["submissions"])
            idb = sorted(self._traj_share(Path(b), "pepper")[0]["submissions"])
            idc = sorted(self._traj_share(Path(c))[0]["submissions"])
        self.assertEqual(ida, idb, "same salt must give the same pseudonyms")
        self.assertNotEqual(ida, idc, "a random salt must not reproduce them")
        self.assertNotIn("pepper", json.dumps(ida))

    def test_spend_share_is_allowlisted_and_carries_no_owners_or_labels(self):
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run([sys.executable, str(ROOT / "metermaid_audit.py"), "--demo", "--days", "30",
                                "--out", td, "--share"], capture_output=True, text=True, check=True, cwd=td)
            payload = json.loads((Path(td) / "share.json").read_text(encoding="utf-8"))
            local = (Path(td) / "audit.json").read_text(encoding="utf-8")
        self.assertEqual(set(payload), self.SPEND_KEYS)
        blob = self._blob(payload)
        for leak in ("@", "jane", "support-triage", "pr-reviewer", "apikey_", "proj_", "ws_"):
            self.assertNotIn(leak, blob, f"share.json leaked {leak!r}")
        self.assertFalse(self._keys(payload) & {"owner", "label", "key_id", "scope_id", "rows"})
        self.assertIn("support-triage", local, "--share implies --anon, which keeps agent labels locally")
        self.assertTrue(payload["findings"])
        for f in payload["findings"]:
            self.assertTrue(f["scope"] == "org" or f["scope"].startswith("agent_"), f["scope"])
        self.assertTrue(all(k["key"].startswith("key_") for k in payload["top_keys_monthly"]))
        self.assertIn("never contains", r.stdout)
        self.assertLessEqual(payload["opportunity"]["low"], payload["opportunity"]["high"])
        self.assertTrue(all(f["evidence_level"] in ("observed", "modeled") for f in payload["findings"]))


class TestOpportunityAccounting(unittest.TestCase):
    """The spend audit once summed every finding into one waste bill and printed a literal
    0.5-1.0 "confidence" per detector as if it were a probability. Findings on one key
    reprice the same tokens, so the sum double-counts; the report now gives a range."""

    def _demo(self, td: str) -> tuple[dict, str]:
        subprocess.run([sys.executable, str(ROOT / "metermaid_audit.py"), "--demo", "--days", "30", "--out", td],
                       check=True, capture_output=True, cwd=td)
        return (json.loads((Path(td) / "audit.json").read_text(encoding="utf-8"))["result"],
                (Path(td) / "audit.md").read_text(encoding="utf-8"))

    def test_headline_is_a_range_not_a_sum(self):
        with tempfile.TemporaryDirectory() as td:
            res, md = self._demo(td)
        op = res["opportunity"]
        priced = [f["monthly_waste"] for f in res["findings"] if f["monthly_waste"] > 0]
        self.assertEqual(op["findings"], len(priced))
        self.assertAlmostEqual(op["low"], max(priced))
        self.assertAlmostEqual(op["naive_sum"], sum(priced))
        self.assertLessEqual(op["low"], op["high"])
        self.assertLessEqual(op["high"], op["naive_sum"])
        self.assertLessEqual(op["high"], res["estimated_spend_monthly"])
        self.assertNotIn("estimated_monthly_waste", res)
        self.assertIn("Opportunity:", md)
        self.assertIn("never the naive sum", md)
        self.assertNotIn("Estimated waste", md)

    def test_high_bound_is_capped_at_each_keys_own_spend(self):
        audit = load("metermaid_audit")
        F = audit.Finding
        fs = [F("L01", "a", "agent-x", 600.0, audit.MODELED, "", ""),
              F("L05", "b", "agent-x", 500.0, audit.MODELED, "", ""),
              F("L10", "c", "agent-y", 100.0, audit.MODELED, "", ""),
              F("L02", "d", "org", 0.0, audit.OBSERVED, "", "")]
        op = audit.opportunity_range(fs, {"agent-x": 800.0, "agent-y": 1000.0}, 5000.0)
        self.assertEqual(op["low"], 600.0)
        self.assertEqual(op["naive_sum"], 1200.0)
        self.assertEqual(op["high"], 900.0, "agent-x's two findings must be capped at its $800 spend")
        self.assertEqual(op["findings"], 3)
        self.assertEqual(audit.opportunity_range([fs[-1]], {}, 5000.0)["findings"], 0)

    def test_every_finding_states_its_evidence_level_and_no_confidence_number(self):
        with tempfile.TemporaryDirectory() as td:
            res, md = self._demo(td)
        for f in res["findings"]:
            with self.subTest(finding=f["id"]):
                self.assertIn(f["evidence_level"], ("observed", "modeled"))
                self.assertNotIn("confidence", f)
                if f["evidence_level"] == "modeled":
                    self.assertTrue(f["assumption"], "a modeled figure must state its assumption")
        self.assertNotIn("Confidence", md)
        self.assertIn("Evidence: modeled", md)
        self.assertIn("- Assumes:", md)


class TestDetectors(unittest.TestCase):
    """The detectors trajectory_audit.py advertises, on hand-built trajectories."""

    def test_loop_retry_and_bloat_are_detected(self):
        msgs = []
        for _ in range(4):
            msgs += [{"role": "assistant", "content": "ls -la"},
                     {"role": "user", "content": "Error: command failed"}]
        msgs += [{"role": "assistant", "content": "cat big.txt"},
                 {"role": "user", "content": "x" * 25_000}]
        with tempfile.TemporaryDirectory() as td:
            res = run_traj(Path(td), {"r": {"messages": msgs, "exit_status": "submitted"}})
        found = " ".join(list(res["submissions"].values())[0]["by_detector"])
        for detector in ("T01", "T02", "T03"):
            self.assertIn(detector, found, f"{detector} not detected")

    def test_context_exhausted_beats_abandoned(self):
        """A top-level exit_status must be read, not just info.exit_status."""
        with tempfile.TemporaryDirectory() as td:
            res = run_traj(Path(td), {"r": submit_run(exit_status="exit_context")})
        found = " ".join(list(res["submissions"].values())[0]["by_detector"])
        self.assertIn("T07", found, "context-exhausted run was not classified from exit_status")
        self.assertNotIn("T06", found)


def parallel_openai_turns(n_turns: int = 3, big: int = 30_000) -> list[dict]:
    """n assistant turns, each issuing the same two tool calls, each answered by two
    role=tool messages delivered in reverse order. The second call's result carries an
    error plus an oversized payload; the first only an error."""
    msgs = []
    for i in range(n_turns):
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"a{i}", "type": "function", "function": {"name": "bash", "arguments": "{\"cmd\": \"pytest tests/a.py\"}"}},
            {"id": f"b{i}", "type": "function", "function": {"name": "bash", "arguments": "{\"cmd\": \"pytest tests/b.py\"}"}}]})
        msgs.append({"role": "tool", "tool_call_id": f"b{i}", "content": "Error: boom B " + "x" * big})
        msgs.append({"role": "tool", "tool_call_id": f"a{i}", "content": "Error: boom A"})
    msgs += [{"role": "assistant", "content": "submit"}, {"role": "user", "content": "done"}]
    return msgs


def parallel_anthropic_turn() -> list[dict]:
    """One assistant turn with two tool_use blocks, answered by one user message whose
    tool_result blocks arrive in reverse order and name their calls by tool_use_id."""
    return [
        {"role": "assistant", "content": [
            {"type": "text", "text": "Checking both."},
            {"type": "tool_use", "id": "u1", "name": "read", "input": {"path": "a.py"}},
            {"type": "tool_use", "id": "u2", "name": "read", "input": {"path": "b.py"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "u2", "content": "B" * 25_000},
            {"type": "tool_result", "tool_use_id": "u1", "content": [{"type": "text", "text": "small a"}]}]},
        {"role": "assistant", "content": "submit"}, {"role": "user", "content": "done"},
    ]


class TestParallelToolCalls(unittest.TestCase):
    """Both message parsers used to attach only the first tool result of a turn and drop
    the rest, so a parallel-call turn lost the oversized outputs and error messages the
    detectors look for. Every call must become its own step with its own observation."""

    def test_trajectory_audit_keeps_every_result_and_matches_by_id(self):
        ta = load("trajectory_audit")
        t = ta.parse_any({"messages": parallel_openai_turns()}, "r", "sub")
        self.assertEqual(len(t.steps), 7, "3 turns x 2 calls + submit")
        # results arrived b-then-a; ids must route them to the right call regardless of order
        for i in range(3):
            self.assertIn("boom A", t.steps[2 * i].observation)
            self.assertNotIn("x" * 100, t.steps[2 * i].observation)
            self.assertIn("boom B", t.steps[2 * i + 1].observation)
            self.assertGreater(len(t.steps[2 * i + 1].observation), 30_000)
        t = ta.parse_any({"messages": parallel_anthropic_turn()}, "r", "sub")
        self.assertEqual(len(t.steps), 3)
        self.assertEqual(t.steps[0].observation, "small a")
        self.assertEqual(len(t.steps[1].observation), 25_000)

    def test_trajectory_audit_detects_the_bloat_a_dropped_result_used_to_hide(self):
        with tempfile.TemporaryDirectory() as td:
            res = run_traj(Path(td), {"r": {"messages": parallel_openai_turns()}})
        sub = list(res["submissions"].values())[0]
        self.assertEqual(sub["mean_steps"], 7)
        self.assertIn("T03", " ".join(sub["by_detector"]), "oversized second result was not detected")

    def test_pipeline_keeps_every_result_and_matches_by_id(self):
        pl = load("pipeline")
        steps = pl.parse_messages(parallel_openai_turns())
        self.assertEqual(len(steps), 7)
        for i in range(3):
            self.assertIn("boom A", steps[2 * i].obs)
            self.assertGreater(len(steps[2 * i + 1].obs), 30_000)
        steps = pl.parse_messages(parallel_anthropic_turn())
        self.assertEqual(len(steps), 3)
        self.assertEqual(steps[0].obs, "small a")
        self.assertEqual(len(steps[1].obs), 25_000)
        run = pl.analyze_run(pl.parse_messages(parallel_openai_turns()), None)
        self.assertGreaterEqual(run["bloat_obs"], 3, "pipeline did not see the oversized results")

    def test_results_without_ids_attach_in_order_and_nothing_is_dropped(self):
        pl = load("pipeline")
        msgs = [{"role": "assistant", "content": [
                    {"type": "tool_use", "name": "bash", "input": {"cmd": "ls"}},
                    {"type": "tool_use", "name": "bash", "input": {"cmd": "pwd"}}]},
                {"role": "tool", "content": "first"}, {"role": "tool", "content": "second"},
                {"role": "tool", "content": "third, with nowhere to go"}]
        steps = pl.parse_messages(msgs)
        self.assertEqual([s.obs for s in steps], ["first", "second\nthird, with nowhere to go"])

    def test_single_call_turns_are_unchanged(self):
        """The common single-call shape parses exactly as before."""
        ta = load("trajectory_audit")
        t = ta.parse_any(submit_run(), "r", "sub")
        self.assertEqual([(s.action, s.observation) for s in t.steps],
                         [("open foo.py", "ok"), ("submit", "done")])


def run_traj_args(tmp: Path, runs: dict[str, dict], *args: str) -> tuple[dict, str, Path]:
    src = tmp / "traj" / "sub"
    src.mkdir(parents=True, exist_ok=True)
    for name, doc in runs.items():
        (src / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    out = tmp / "out"
    subprocess.run([sys.executable, str(ROOT / "trajectory_audit.py"), str(tmp / "traj"), "--out", str(out), *args],
                   check=True, capture_output=True)
    return (json.loads((out / "trajectory-audit.json").read_text(encoding="utf-8")),
            (out / "trajectory-audit.md").read_text(encoding="utf-8"), out)


def steps_run(actions: list[str], **extra) -> dict:
    msgs = []
    for a in actions:
        msgs += [{"role": "assistant", "content": a}, {"role": "user", "content": "ok"}]
    return {"messages": msgs, **extra}


class TestTasksAndAttempts(unittest.TestCase):
    """The task is the unit of economics: every attempt at the same job, restarts included."""

    def test_explicit_ids_group_attempts_and_price_the_restart(self):
        first = steps_run(["ls", "cat a.py", "pytest", "edit a.py"], instance_id="acme__1", run_id="r1", attempt=1, resolved=False)
        second = steps_run(["ls", "cat a.py", "pytest", "submit"], instance_id="acme__1", run_id="r2", attempt=2, resolved=True)
        with tempfile.TemporaryDirectory() as td:
            # file names deliberately out of order: the attempt field must decide
            res, md, out = run_traj_args(Path(td), {"b_second": second, "a_first": first})
            tasks = [json.loads(l) for l in (out / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
            attempts = [json.loads(l) for l in (out / "attempts.jsonl").read_text(encoding="utf-8").splitlines()]
        tk = res["tasks"]
        self.assertEqual((tk["tasks"], tk["attempts"], tk["tasks_restarted"]), (1, 2, 1))
        self.assertEqual(tk["id_sources"], {"task_id": {"instance_id": 2}, "attempt_id": {"run_id": 2}, "outcome": {"resolved": 2}})
        self.assertEqual(tasks[0]["outcome"], "success", "a task whose later attempt succeeded is a success")
        self.assertEqual(tasks[0]["attempts"], ["r1", "r2"])
        by_id = {a["attempt_id"]: a for a in attempts}
        self.assertEqual((by_id["r1"]["attempt_index"], by_id["r2"]["attempt_index"]), (1, 2))
        self.assertEqual(by_id["r2"]["retry_of"], "r1")
        self.assertEqual(by_id["r2"]["repeated_prefix_steps"], 3, "the restart redid ls, cat, pytest")
        self.assertEqual(tk["redone_steps"], 3)
        self.assertAlmostEqual(tk["restart_cost"], by_id["r2"]["cost"])
        self.assertAlmostEqual(tk["cost_per_successful_task"], tk["total_cost"], msg="both attempts in the numerator")
        self.assertIn("1 tasks restarted", md)

    def test_filename_is_the_fallback_task_id_and_similar_text_is_not_grouped(self):
        same = steps_run(["ls", "pytest", "submit"])
        with tempfile.TemporaryDirectory() as td:
            res, md, _ = run_traj_args(Path(td), {"repo__7": same, "repo__8": dict(same)})
        tk = res["tasks"]
        self.assertEqual((tk["tasks"], tk["attempts"], tk["tasks_restarted"]), (2, 2, 0))
        self.assertEqual(tk["id_sources"]["task_id"], {"filename": 2})
        self.assertIn("filename: 2", md)

    def test_task_id_field_override(self):
        with tempfile.TemporaryDirectory() as td:
            res, _, _ = run_traj_args(Path(td), {"x": steps_run(["ls", "submit"], ticket="T-1", instance_id="ignored-a"),
                                                  "y": steps_run(["ls", "submit"], ticket="T-1", instance_id="ignored-b")},
                                      "--task-id-field", "ticket")
        self.assertEqual(res["tasks"]["tasks"], 1)
        self.assertEqual(res["tasks"]["id_sources"]["task_id"], {"ticket": 2})

    def test_missing_outcome_is_unknown_not_failure_and_ratio_is_undefined_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            res, md, _ = run_traj_args(Path(td), {"u": steps_run(["ls", "submit"], instance_id="1"),
                                                   "f": steps_run(["ls", "submit"], instance_id="2", resolved=0)})
        tk = res["tasks"]
        self.assertEqual((tk["tasks_success"], tk["tasks_failure"], tk["tasks_unknown"]), (0, 1, 1))
        self.assertIsNone(tk["cost_per_successful_task"])
        self.assertIn("no task succeeded", tk["cost_per_successful_task_basis"])
        self.assertEqual(tk["outcome_coverage"], 0.5)
        self.assertIn("undefined", md)
        with tempfile.TemporaryDirectory() as td:
            res, _, _ = run_traj_args(Path(td), {"u": steps_run(["ls", "submit"], instance_id="1")})
        self.assertIn("no task carries an outcome", res["tasks"]["cost_per_successful_task_basis"])

    def test_duplicate_attempt_ids_are_dropped_once_and_listed(self):
        doc = steps_run(["ls", "submit"], instance_id="1", run_id="same")
        with tempfile.TemporaryDirectory() as td:
            res, md, _ = run_traj_args(Path(td), {"a": doc, "b": dict(doc)})
        self.assertEqual(res["trajectories"], 1)
        self.assertEqual(res["intake"]["duplicate_attempts_dropped"], 1)
        self.assertEqual(res["intake"]["duplicates"][0]["attempt_id"], "same")
        self.assertIn("1 duplicate attempt ids dropped", md)

    def test_events_file_is_opt_in_and_holds_hashes_not_output(self):
        doc = steps_run(["cat secrets.txt"], instance_id="1")
        doc["messages"][1]["content"] = "TOP-SECRET-PAYLOAD " * 50
        with tempfile.TemporaryDirectory() as td:
            _, _, out = run_traj_args(Path(td), {"r": doc})
            self.assertFalse((out / "events.jsonl").exists())
        with tempfile.TemporaryDirectory() as td:
            _, _, out = run_traj_args(Path(td), {"r": doc}, "--events")
            rows = [json.loads(l) for l in (out / "events.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["action"], "cat secrets.txt")
        self.assertEqual(rows[0]["obs_chars"], len("TOP-SECRET-PAYLOAD " * 50))
        self.assertNotIn("TOP-SECRET", json.dumps(rows))
        self.assertEqual(rows[0]["parent_id"], rows[0]["event_id"].rsplit("#", 1)[0])

    def test_schema_outcome_and_task_rules(self):
        sc = load("schema")
        self.assertEqual(sc.outcome_of({"resolved": True}), ("success", "resolved"))
        self.assertEqual(sc.outcome_of({"target": 0}), ("failure", "target"))
        self.assertEqual(sc.outcome_of({"resolved": "None"}), ("unknown", None))
        self.assertEqual(sc.outcome_of({"resolved": 0.5}), ("unknown", None))
        self.assertEqual(sc.outcome_of({}), ("unknown", None))
        A = sc.Attempt
        mk = lambda i, o, c: A(f"a{i}", "t", "w", i, None if i == 1 else f"a{i-1}", "f", "p", "instance_id", "run_id",
                               3, c, "reported", None, None, o, "resolved", None)
        tasks = sc.build_tasks([mk(1, "failure", 1.0), mk(2, "unknown", 2.0)])
        self.assertEqual(tasks[0].outcome, "unknown", "failure plus unknown is unknown, not failure")
        self.assertEqual(tasks[0].restart_cost, 2.0)
        self.assertEqual(sc.build_tasks([mk(1, "failure", 1.0), mk(2, "failure", 2.0)])[0].outcome, "failure")
        self.assertEqual(sc.common_prefix(["a", "b", "c"], ["a", "b", "x"]), 2)


class TestComparabilityWithIndex(unittest.TestCase):
    """trajectory_audit.py must count what pipeline.py counts, or a local audit
    cannot be compared against the published Index — which the README invites."""

    def test_edit_thrash_is_reported_but_not_costed(self):
        msgs = []
        for _ in range(10):
            msgs += [{"role": "assistant", "content": "edit src/foo.py"},
                     {"role": "user", "content": "edited"}]
        msgs += [{"role": "assistant", "content": "submit"}, {"role": "user", "content": "done"}]
        with tempfile.TemporaryDirectory() as td:
            res = run_traj(Path(td), {"r": {"messages": msgs, "exit_status": "submitted"}})
        sub = list(res["submissions"].values())[0]
        self.assertIn("T13", " ".join(sub["by_detector"]), "edit thrash should still be reported")
        self.assertEqual(sub["waste_share"], 0, "edit thrash must not count as mechanical waste")
        self.assertEqual(sub["trajs_with_any_finding"], 0, "edit thrash must not count as a finding")

    def test_literal_none_exit_status_is_ignored(self):
        """pipeline.py filters the string "None"; so must this, or the same run is
        scored abandoned here and submitted there."""
        with tempfile.TemporaryDirectory() as td:
            res = run_traj(Path(td), {"r": submit_run(exit_status="None")})
        sub = list(res["submissions"].values())[0]
        self.assertEqual(sub["sunk_share"], 0, '"None" exit_status was treated as a real status')

    def test_detector_groups_are_disjoint(self):
        ta = load("trajectory_audit")
        groups = [set(ta.MECH), set(ta.SUNK), set(ta.EXCLUDED_FROM_FINDING)]
        for a, b in ((0, 1), (0, 2), (1, 2)):
            self.assertFalse(groups[a] & groups[b], "detector groups overlap")


class TestReportRendering(unittest.TestCase):
    def test_resolve_line_keeps_the_overall_rate(self):
        """When no flagged run carries a resolve label, the known overall rate
        must still be printed rather than replaced with 'n/a'."""
        msgs = []
        for _ in range(10):                      # thrash only: reported, never flagged
            msgs += [{"role": "assistant", "content": "edit src/foo.py"},
                     {"role": "user", "content": "edited"}]
        msgs += [{"role": "assistant", "content": "submit"}, {"role": "user", "content": "done"}]
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            run_traj(tmp, {"a": {"messages": msgs, "exit_status": "submitted", "resolved": True},
                           "b": {"messages": msgs, "exit_status": "submitted", "resolved": False}})
            line = next(l for l in (tmp / "out" / "trajectory-audit.md").read_text(encoding="utf-8")
                        .splitlines() if l.startswith("- resolve rate:"))
        self.assertIn("overall", line)
        self.assertNotIn("n/a", line)


class TestRunLengthCurve(unittest.TestCase):
    """The per-quintile curve trajectory_audit.py computes locally, and the report built from it."""

    def _many_runs(self, n=40, resolved=None):
        runs = {}
        for i in range(n):
            msgs = []
            for j in range(3 + i):                      # increasing step counts
                msgs += [{"role": "assistant", "content": f"cmd {j}"},
                         {"role": "user", "content": "ok " + "x" * (40 * j)}]
            msgs += [{"role": "assistant", "content": "submit"}, {"role": "user", "content": "done"}]
            doc = {"messages": msgs, "exit_status": "submitted"}
            if resolved is not None:
                doc["resolved"] = resolved(i)
            runs[f"r{i:03d}"] = doc
        return runs

    def test_curve_has_five_buckets_covering_every_run(self):
        with tempfile.TemporaryDirectory() as td:
            res = run_traj(Path(td), self._many_runs())
        curve = res["curve"]
        self.assertEqual([c["q"] for c in curve], [1, 2, 3, 4, 5])
        self.assertEqual(sum(c["n"] for c in curve), res["trajectories"])
        self.assertAlmostEqual(sum(c["cost_share"] for c in curve), 1.0, places=6)

    def test_buckets_are_ordered_by_run_length(self):
        with tempfile.TemporaryDirectory() as td:
            res = run_traj(Path(td), self._many_runs())
        highs = [c["steps_hi"] for c in res["curve"]]
        self.assertEqual(highs, sorted(highs), "quintiles are not ordered by step count")
        for a, b in zip(res["curve"], res["curve"][1:]):
            self.assertLessEqual(a["steps_hi"], b["steps_lo"], "buckets overlap on step count")

    def test_ntile_matches_sql_semantics(self):
        """ntile(5) gives earlier buckets the remainder; the Index relies on that split."""
        ta = load("trajectory_audit")
        self.assertEqual([len(b) for b in ta._ntile(list(range(13)), 5)], [3, 3, 3, 2, 2])
        self.assertEqual([len(b) for b in ta._ntile(list(range(10)), 5)], [2, 2, 2, 2, 2])

    def test_no_curve_below_the_minimum_run_count(self):
        """Too few runs must produce nothing rather than five noisy buckets."""
        with tempfile.TemporaryDirectory() as td:
            res = run_traj(Path(td), self._many_runs(n=6))
        self.assertEqual(res["curve"], [])

    def test_report_renders_without_outcome_labels(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            res = run_traj(tmp, self._many_runs())
            audit = tmp / "audit.json"
            audit.write_text(json.dumps(res), encoding="utf-8")
            out = tmp / "benchmark.html"
            subprocess.run([sys.executable, str(ROOT / "benchmark.py"), str(audit),
                            "--index", str(ROOT / "report" / "index.json"), "--out", str(out),
                            "--org", "Acme & Co"], check=True, capture_output=True)
            html = out.read_text(encoding="utf-8")
        self.assertIn("no task outcomes", html, "missing outcomes should be called out, not hidden")
        self.assertIn("Acme &amp; Co", html, "org name must be HTML-escaped")
        self.assertIn("public groups", html, "report did not position against the Index")

    def _render(self, tmp: Path, res: dict) -> str:
        audit = tmp / "audit.json"
        audit.write_text(json.dumps(res), encoding="utf-8")
        out = tmp / "benchmark.html"
        subprocess.run([sys.executable, str(ROOT / "benchmark.py"), str(audit),
                        "--index", str(ROOT / "report" / "index.json"), "--out", str(out)],
                       check=True, capture_output=True)
        return out.read_text(encoding="utf-8")

    def test_report_states_the_yield_ratio_when_outcomes_exist(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            res = run_traj(tmp, self._many_runs(resolved=lambda i: i % 3 == 0))  # resolves in every bucket
            self.assertIsNotNone(res["curve"][0]["resolve"])
            html = self._render(tmp, res)
        self.assertNotIn("no task outcomes", html)
        self.assertIn("resolved tasks than a dollar in the shortest", html)

    def test_a_tail_that_resolves_nothing_is_stated_not_dropped(self):
        """resolved-per-dollar of zero is the strongest form of the finding, not a missing value."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            res = run_traj(tmp, self._many_runs(resolved=lambda i: i < 12))  # only short runs resolve
            self.assertEqual(res["curve"][-1]["resolved_per_dollar"], 0)
            html = self._render(tmp, res)
        self.assertIn("resolved <b>nothing at all</b>", html)

    def test_benchmark_ranks_against_the_published_index(self):
        bm = load("benchmark")
        index = json.loads((ROOT / "report" / "index.json").read_text(encoding="utf-8"))
        dist = bm.index_distributions(index)
        self.assertEqual(len(dist["waste_share"]), len(index["groups"]))
        self.assertTrue(dist["tail_share"], "no longest-fifth population to rank against")
        low = bm.rank(0.0, dist["waste_share"])
        high = bm.rank(1.0, dist["waste_share"])
        self.assertEqual(low["below"], 0)
        self.assertEqual(high["below"], high["total"])
        self.assertIn("lower than", bm.phrase(low))
        self.assertIn("higher than", bm.phrase(high))


@unittest.skipUnless(have("duckdb") and have("pyarrow"), "needs duckdb and pyarrow")
class TestPipelineReport(unittest.TestCase):
    def _shard(self, tmp: Path, pl, **overrides):
        runs = [pl.Run(dataset="SWE-bench/SWE-smith-trajectories", config="default", split="tool",
                       run_id=f"r{i}", model="claude-3-7-sonnet-20250219", scaffold="swe-agent/tool",
                       resolved=(i % 2 == 0), exit_status=None, steps=10, calls=10,
                       est_tokens_in=1000, est_tokens_out=100, est_cost=1.0, terminal="submitted",
                       loop_steps=0, loop_worst=0, loop_worst_action="", retry_steps=0,
                       bloat_obs=0, bloat_excess_tokens=0, thrash_steps=0, mech_waste_steps=0,
                       mech_waste_cost=0.0, sunk=False, any_finding=False, **overrides)
                for i in range(300)]
        pl.write_parquet(runs, tmp / "runs" / "shard.parquet")

    def test_report_survives_a_dataset_with_no_failed_runs(self):
        """SWE-smith groups are all 0% failed-run, so SUM over an all-false CASE
        returns NULL; dividing it used to raise TypeError."""
        pl = load("pipeline")
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._shard(tmp, pl)
            with contextlib.redirect_stdout(io.StringIO()):
                pl.report(tmp, tmp / "out")
            text = (tmp / "out" / "index.md").read_text(encoding="utf-8")
        self.assertIn("300 runs", text)
        self.assertIn("spent on runs that ended without a result", text)

    def test_report_refuses_an_empty_data_directory(self):
        pl = load("pipeline")
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit), contextlib.redirect_stdout(io.StringIO()):
                pl.report(Path(td), Path(td) / "out")


class TestPublishedIndexMatchesCode(unittest.TestCase):
    """The checked-in report is the thing the README and launch copy quote.
    These guard the drift that shipped once already."""

    @classmethod
    def setUpClass(cls):
        cls.index = json.loads((ROOT / "report" / "index.json").read_text(encoding="utf-8"))
        cls.groups = cls.index["groups"]

    def test_open_swe_labels_match_the_code(self):
        pl = load("pipeline")
        published = {g["model"] for g in self.groups if g["dataset"] == "nvidia/Open-SWE-Traces"}
        self.assertEqual(published, set(pl.OPEN_SWE_MODEL_BY_CONFIG.values()),
                         "report labels Open-SWE rows differently from pipeline.py")

    def test_open_swe_labels_name_no_model(self):
        """The dataset card does not attribute a model per config; the labels must not guess."""
        pl = load("pipeline")
        for label in pl.OPEN_SWE_MODEL_BY_CONFIG.values():
            self.assertIn("see card", label, f"{label!r} attributes a model the card does not")

    def test_total_runs_is_the_sum_of_groups(self):
        self.assertEqual(self.index["total_runs"], sum(g["runs"] for g in self.groups))

    def test_readme_counts_match_the_report(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"{self.index['total_runs']:,} runs", readme)
        self.assertIn(f"{len(self.groups)} dataset/model/scaffold groups", readme)
        self.assertIn(f"{len({g['model'] for g in self.groups})} model labels", readme)
        self.assertIn(f"{len({g['dataset'] for g in self.groups})} datasets", readme)

    def test_notes_open_swe_run_count_matches(self):
        notes = (ROOT / "report" / "notes.md").read_text(encoding="utf-8")
        n = sum(g["runs"] for g in self.groups if g["dataset"] == "nvidia/Open-SWE-Traces")
        self.assertIn(f"{n:,} runs ride on that label", notes)

    def test_launch_copy_headline_run_count_matches(self):
        launch = (ROOT / "launch.md").read_text(encoding="utf-8")
        self.assertIn(f"{self.index['total_runs']:,}", launch)
        self.assertNotIn("4,000 public", launch,
                         "launch copy still quotes the retracted pilot as a current finding")


class TestClaimsLedger(unittest.TestCase):
    """supported.json says what the tools do. Copy in this repository may not claim more.
    The website is meant to run the same check against its pages."""

    COPY = ["README.md", "launch.md"]

    @classmethod
    def setUpClass(cls):
        cls.ledger = json.loads((ROOT / "supported.json").read_text(encoding="utf-8"))

    def test_repository_copy_claims_nothing_the_code_does_not_do(self):
        phrases = [(group, p) for group, lst in self.ledger["never_claim"].items()
                   if not group.startswith("_") for p in lst]
        offences = []
        for name in self.COPY:
            for n, line in enumerate((ROOT / name).read_text(encoding="utf-8").splitlines(), 1):
                low = line.lower()
                for group, p in phrases:
                    if p.lower() in low:
                        offences.append(f"{name}:{n} [{group}] {p!r}: {line.strip()[:100]}")
        self.assertEqual(offences, [], "copy claims something supported.json says does not exist:\n" + "\n".join(offences))

    def test_readme_names_every_supported_provider_and_format(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for p in self.ledger["spend_audit"]["providers"]:
            self.assertIn(p, readme)
        for f in self.ledger["trajectory_audit"]["formats"]:
            self.assertIn(f, readme)
        for o in self.ledger["outputs"]:
            self.assertIn(o.split()[0] if o.endswith((".html", ".json")) else o, readme)

    def test_ledger_matches_the_spend_audit_connectors(self):
        """The providers the ledger lists are exactly the ones the spend audit can fetch."""
        audit = load("metermaid_audit")
        fetchers = {n.removeprefix("fetch_").removesuffix("_usage") for n in dir(audit)
                    if n.startswith("fetch_") and n.endswith("_usage")}
        self.assertEqual(fetchers, {p.lower() for p in self.ledger["spend_audit"]["providers"]})

    def test_ledger_never_claim_phrases_are_not_in_supported(self):
        """A phrase cannot be both supported and forbidden."""
        supported = json.dumps({k: v for k, v in self.ledger.items() if k != "never_claim"}).lower()
        for group, lst in self.ledger["never_claim"].items():
            if group.startswith("_"):
                continue
            for p in lst:
                self.assertNotIn(p.lower(), supported, f"{p!r} is listed as both supported and never_claim")


if __name__ == "__main__":
    unittest.main(verbosity=2)
