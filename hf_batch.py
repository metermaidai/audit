#!/usr/bin/env python3
"""
hf_batch.py — sweep a list of Hugging Face trajectory datasets: pull N runs from every split,
run trajectory_audit.py per dataset, and zip the results for hand-back.

    python -m pip install datasets requests
    python hf_batch.py                       # default list below, 5,000 runs per split
    python hf_batch.py --limit 20000         # bigger sample
    python hf_batch.py --only nvidia/Open-SWE-Traces nebius/SWE-rebench-openhands-trajectories
    python hf_batch.py --inspect             # print columns/splits for every dataset, pull nothing

Output: results/<dataset>/trajectory-audit.{md,json} plus results/unparsed-samples/ (one raw row per
dataset that failed to parse, so a parser can be added), and results.zip.
Pulled runs go to hf/ and are deleted per dataset after auditing unless --keep.
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT = [
    "nebius/SWE-agent-trajectories",
    "SWE-bench/SWE-smith-trajectories",
    "nebius/SWE-rebench-openhands-trajectories",
    "nvidia/Open-SWE-Traces",
    "nvidia/SWE-Hero-openhands-trajectories",
    "nvidia/SWE-Zero-openhands-trajectories",
    "thoughtworks/agentic-coding-trajectories",
    "SWE-Gym/OpenHands-Sampled-Trajectories",
    "open-thoughts/AgentTrove",
    "ricdomolm/mini-coder-trajs-400k",
    "AlienKevin/SWE-ZERO-12M-trajectories",
]


def splits_for(ds: str) -> list[str]:
    from datasets import get_dataset_split_names
    try:
        return get_dataset_split_names(ds)
    except Exception as e:  # config-required datasets
        msg = str(e)
        print(f"  could not list splits for {ds}: {msg[:200]}", file=sys.stderr)
        return ["train"]


def run(cmd: list[str]) -> int:
    print("  $", " ".join(cmd), file=sys.stderr)
    return subprocess.call(cmd)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5000, help="runs per split")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--sample", type=int, default=0, help="pull N full raw rows per split into results/samples and zip; no audit")
    ap.add_argument("--keep", action="store_true", help="keep pulled JSON under hf/")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    datasets = a.only or DEFAULT
    out = Path(a.out); out.mkdir(exist_ok=True)
    (out / "unparsed-samples").mkdir(exist_ok=True)
    summary = {}
    for ds in datasets:
        tag = ds.replace("/", "__")
        print(f"\n=== {ds}", file=sys.stderr)
        splits = splits_for(ds)
        print(f"  splits: {splits}", file=sys.stderr)
        if a.inspect:
            run([sys.executable, str(HERE / "hf_pull.py"), ds, "--split", splits[0], "--inspect"])
            continue
        if a.sample:
            from datasets import load_dataset, get_dataset_config_names
            (out / "samples").mkdir(exist_ok=True)
            try:
                configs = get_dataset_config_names(ds)
            except Exception:
                configs = [None]
            for cfg in configs[:4]:
                for sp in splits:
                    try:
                        it = iter(load_dataset(ds, cfg, split=sp, streaming=True))
                        rows = [next(it) for _ in range(a.sample)]
                    except Exception as e:
                        rows = [{"_error": str(e)[:500]}]
                    name = f"{tag}__{cfg or 'default'}__{sp}.json"
                    (out / "samples" / name).write_text(json.dumps(rows, default=str), encoding="utf-8")
                    print(f"  sampled {name}", file=sys.stderr)
            summary[ds] = {"status": "sampled", "configs": configs[:4], "splits": splits}
            continue
        hf_dir = Path("hf") / tag
        if hf_dir.exists():
            shutil.rmtree(hf_dir)
        pulled_any = False
        for sp in splits:
            rc = run([sys.executable, str(HERE / "hf_pull.py"), ds, "--split", sp, "--limit", str(a.limit), "--out", "hf"])
            pulled_any = pulled_any or rc == 0
        if not pulled_any or not hf_dir.exists():
            summary[ds] = {"status": "pull_failed"}
            continue
        ds_out = out / tag
        rc = run([sys.executable, str(HERE / "trajectory_audit.py"), str(hf_dir), "--label-by-parent", "--out", str(ds_out)])
        rep = ds_out / "trajectory-audit.json"
        if rc == 0 and rep.exists():
            r = json.loads(rep.read_text(encoding="utf-8"))
            summary[ds] = {"status": "ok", "trajectories": r["trajectories"], "waste_share": r["waste_share"], "sunk_share": r["sunk_share"],
                           "submissions": {k: {"trajs": v["trajectories"], "waste": v["waste_share"], "sunk": v["sunk_share"],
                                               "resolve": v.get("resolve_rate"), "resolve_flag": v.get("resolve_rate_with_findings"),
                                               "resolve_clean": v.get("resolve_rate_without_findings")} for k, v in r["submissions"].items()}}
        else:
            summary[ds] = {"status": "audit_failed_or_unparsed"}
            # keep one raw row so a parser can be written
            sample = next(hf_dir.rglob("*.json"), None)
            if sample:
                shutil.copy(sample, out / "unparsed-samples" / f"{tag}.json")
        if not a.keep:
            shutil.rmtree(hf_dir, ignore_errors=True)

    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with zipfile.ZipFile("results.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in out.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(out.parent))
    print("\nwrote results.zip — send this back", file=sys.stderr)
    for ds, s in summary.items():
        print(f"{ds}: {s.get('status')} " + (f"{s['trajectories']} runs, mech {s['waste_share']:.0%}, sunk {s['sunk_share']:.0%}" if s.get("status") == "ok" else ""))


if __name__ == "__main__":
    main()
