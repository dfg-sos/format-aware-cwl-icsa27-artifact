"""Run the fault-injection scenarios (RQ1) and keep their console output for the artifact.

    uv run python bench/scenarios.py [--repeat 3] [--only A2,B]

Needs a running format service (`--format-service-url`, default $SOS_FFS_URL or localhost:8000) with
fixtures/mappings mounted. Each scenario is a fixture from fixtures/ (a copy of the runner's
tests/fixtures, frozen for this artifact) run as `baseline` (`--format-validation off`: plain
cwltool, but the timing log records which steps ran), in `basic`, `structural` and `full` mode with
the default `fail` policy, in the extra flag variants some scenarios list, and through
`cwl-format-lint`. Every run is repeated `--repeat` times; the outcome (exit code, non-SUCCESS
checks, steps that ran) must be the same in every repetition and match the expected exit code
(those of the runner's tests/test_integration.py).
Writes to `<--out>/`:
  <ID>/command.txt    the commands, relative to the repository root
  <ID>/<run>.log      console output (stdout and stderr) of the first repetition
  <ID>/outcome.json   per run: expected and observed exit codes, wall seconds, failed checks, steps not run
  summary.csv         one row per scenario and run
  env.txt             date, host, repository commit, service URL and image, versions
Violations are printed and make the exit code 1.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path("fixtures")
BIN = Path(sys.executable).parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MODES = ("basic", "structural", "full")

# id, workflow, job, expected exit per run (baseline, basic, structural, full, lint), extra runs {name: (args, exit)}
# lint None: not linted (the document has no $schemas)
SCENARIOS = [
    # faults
    ("D", "d_shapefile_to_geotiff.cwl", "jobs/d.yml", (1, 1, 1, 1, 1), {}),
    ("A1", "a_relabel.cwl", "jobs/a1.yml", (0, 1, 1, 1, 0), {}),
    ("A2", "a_relabel.cwl", "jobs/a2.yml", (0, 0, 0, 1, 0), {}),
    ("A2-docker", "a_relabel_docker.cwl", "jobs/a2.yml", (0, 0, 0, 1, 0), {}),
    ("B", "b_crs.cwl", "jobs/b.yml", (0, 0, 0, 1, 0), {}),
    ("C", "c_geometry.cwl", "jobs/c_points.yml", (0, 0, 0, 1, 0), {}),
    ("I1", "i_input.cwl", "jobs/i1.yml", (0, 1, 1, 1, 0), {}),
    ("I2", "i_input.cwl", "jobs/i2.yml", (0, 0, 0, 1, 0), {}),
    ("J", "i_input.cwl", "jobs/j.yml", (0, 0, 0, 1, 0), {}),
    # controls
    ("C-roads", "c_geometry.cwl", "jobs/c_roads.yml", (0, 0, 0, 0, 0), {}),
    ("D-vector", "d_shapefile_to_vector.cwl", "jobs/d.yml", (0, 0, 0, 0, 0), {}),
    ("E", "e_unannotated.cwl", None, (0, 0, 0, 0, None), {}),
    ("I-ok", "i_input.cwl", "jobs/i_ok.yml", (0, 0, 0, 0, 0), {}),
    # limits of the service
    ("G", "g_unsupported_format.cwl", None, (0, 0, 0, 0, 0), {"uncertain-fail": (["--format-uncertain", "fail"], 1)}),
    (
        "H",
        "h_invalid_metadata.cwl",
        "jobs/b.yml",
        (0, 0, 0, 1, 0),
        {"full-service-error-warn": (["--format-validation-mode", "full", "--format-service-error", "warn"], 0)},
    ),
]
LINT_ONLY = [("F", "f_edam_online.cwl", 1)]


def steps_of(workflow: Path) -> list[str]:
    doc = YAML(typ="safe").load(workflow.read_text())
    if doc.get("class") == "Workflow":
        return list(doc["steps"])
    return [workflow.name]  # a single tool is logged under its file name


def outcome(log: Path, steps: list[str]) -> dict:
    """Failed checks and steps not run, from the runner's timing log."""
    records = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    ran = {r["step"] for r in records if r["record"] == "main"}
    failed = [
        {k: r[k] for k in ("step", "port", "direction", "file", "result", "message")}
        for r in records
        if r["record"] == "check" and r["result"] != "SUCCESS"
    ]
    return {"failed_checks": failed, "steps_not_run": [s for s in steps if s not in ran]}


def comparable(o: dict) -> tuple:
    """The part of an outcome that must not change between repetitions (messages carry temp paths)."""
    checks = tuple((c["step"], c["port"], c["direction"], c["result"]) for c in o.get("failed_checks", []))
    return o["exit"], checks, tuple(o.get("steps_not_run", []))


def run_once(cmd: list[str]) -> tuple[int, float, str]:
    t0 = time.perf_counter()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, time.perf_counter() - t0, ANSI.sub("", p.stdout + p.stderr)


def docker_available() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--format-service-url", default=os.environ.get("SOS_FFS_URL", "http://localhost:8000"))
    ap.add_argument("--service-image", default="", help="image (digest) of the service, recorded in env.txt")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--only", default=None, help="comma-separated scenario IDs")
    ap.add_argument("--out", type=Path, default=ROOT / "bench" / "results" / "scenarios")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    service = ["--format-service-url", a.format_service_url]
    runner, lint = str(BIN / "cwl-format-aware-runner"), str(BIN / "cwl-format-lint")
    has_docker = docker_available()
    a.out.mkdir(parents=True, exist_ok=True)

    plans = []  # (id, workflow, steps, [(run name, argv without outdir/log, expected exit, uses runner)])
    for sid, wf, job, (base, *modes, lint_rc), extra in SCENARIOS:
        files = [str(FIXTURES / wf), *([str(FIXTURES / job)] if job else [])]
        runs = [("baseline", ["--format-validation", "off", *files], base, True)]
        runs += [(m, ["--format-validation-mode", m, *files], rc, True) for m, rc in zip(MODES, modes, strict=True)]
        runs += [(name, [*args, *files], rc, True) for name, (args, rc) in extra.items()]
        if lint_rc is not None:
            runs.append(("lint", [str(FIXTURES / wf)], lint_rc, False))
        plans.append((sid, wf, steps_of(ROOT / FIXTURES / wf), runs))
    for sid, wf, lint_rc in LINT_ONLY:
        plans.append((sid, wf, [], [("lint", [str(FIXTURES / wf)], lint_rc, False)]))

    problems, summary = [], []
    for sid, wf, steps, runs in plans:
        if only and sid not in only:
            continue
        if "docker" in wf and not has_docker:
            print(f"{sid}: skipped, docker daemon not available")
            continue
        d = a.out / sid
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir()
        commands, outcomes = [], {}
        for name, argv, expected, is_runner in runs:
            shown = ["cwl-format-aware-runner" if is_runner else "cwl-format-lint", *service, *argv]
            commands.append(f"# {name}\n{' '.join(shown)}\n")
            reps = []
            for rep in range(a.repeat):
                with tempfile.TemporaryDirectory() as tmp:
                    log = Path(tmp) / "t.jsonl"
                    extra = ["--outdir", f"{tmp}/out", "--format-timing-log", str(log)] if is_runner else []
                    rc, wall, console = run_once([runner if is_runner else lint, *service, *extra, *argv])
                    o = {"exit": rc, "wall_s": round(wall, 3), **(outcome(log, steps) if is_runner else {})}
                if rep == 0:
                    (d / f"{name}.log").write_text(console)
                reps.append(o)
            first = reps[0]
            consistent = all(comparable(o) == comparable(first) for o in reps)
            outcomes[name] = {
                "expected_exit": expected,
                **first,
                "exit_per_rep": [o["exit"] for o in reps],
                "wall_s_per_rep": [o["wall_s"] for o in reps],
                "consistent": consistent,
            }
            if first["exit"] != expected:
                problems.append(f"{sid} {name}: exit {first['exit']}, expected {expected}")
            if not consistent:
                problems.append(f"{sid} {name}: outcome differs between repetitions")
            stopped = first.get("failed_checks", [])
            summary.append(
                {
                    "id": sid,
                    "run": name,
                    "expected_exit": expected,
                    "exit": first["exit"],
                    "consistent": consistent,
                    "failed_check": "; ".join(
                        f"{c['step']}/{c['port']} {c['direction']} {c['result']}" for c in stopped
                    ),
                    "steps_not_run": " ".join(first.get("steps_not_run", [])),
                    "wall_s": first["wall_s"],
                }
            )
            print(
                f"{sid:10} {name:24} exit {first['exit']} (expected {expected}){'' if consistent else ' INCONSISTENT'}"
            )
        (d / "command.txt").write_text("\n".join(commands))
        (d / "outcome.json").write_text(json.dumps({"id": sid, "workflow": wf, "runs": outcomes}, indent=2) + "\n")

    if summary:
        with open(a.out / "summary.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(summary[0]))
            w.writeheader()
            w.writerows(summary)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "diff", "--quiet"], cwd=ROOT).returncode != 0
    versions = subprocess.run([runner, "--version"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    (a.out / "env.txt").write_text(
        f"date: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\nhost: {platform.node()}\n"
        f"platform: {platform.platform()}\npython: {platform.python_version()}\n"
        f"repo: {commit}{' (dirty)' if dirty else ''}\nservice: {a.format_service_url} {a.service_image}\n"
        f"repeat: {a.repeat}\ndocker: {has_docker}\ncwltool: {versions}\n"
    )
    for p in problems:
        print("FAILED:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
