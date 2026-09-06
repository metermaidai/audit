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
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["metermaid_audit.py", "trajectory_audit.py", "pipeline.py",
           "hf_pull.py", "hf_batch.py", "download_logs.py"]


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

    def test_anon_strips_identifiers(self):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([sys.executable, str(ROOT / "metermaid_audit.py"), "--demo",
                            "--days", "30", "--anon", "--out", td],
                           check=True, capture_output=True, cwd=td)
            blob = (Path(td) / "audit.json").read_text(encoding="utf-8")
            for secret in ("sk-ant-", "sk-admin", "@"):
                self.assertNotIn(secret, blob, f"--anon leaked {secret!r}")


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
