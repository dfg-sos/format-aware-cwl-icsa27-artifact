"""Run the fault-injection scenarios (RQ1) and keep their console output for the artifact.

    uv run python scenarios/run.py [--repeat 3] [--only F3.2,F4.1]

Needs a running format service (`--format-service-url`, default $SOS_FFS_URL or localhost:8000) built from
plugins/format-validator-bio, with mappings/ mounted (README.md). The scenarios, their fixtures and expected
exit codes are listed in scenarios/scenarios.yml. Each scenario runs in the variants it lists:
`off` (`--format-validation off`: plain cwltool, but the timing log records which steps ran), `basic`,
`structural` and `full` mode with
the default `fail` policy, extra flag variants, and `lint` (`cwl-format-lint`). Every run is repeated
`--repeat` times; the outcome (exit code, non-SUCCESS checks, steps that ran) must be the same in every
repetition and match the expected exit code.
Writes to `<--out>/`:
  <ID>/command.txt    the commands, relative to the repository root
  <ID>/<run>.log      console output (stdout and stderr) of the first repetition
  <ID>/outcome.json   per run: expected and observed exit codes, wall seconds, failed checks, steps not run
  matrix.csv, .md     one row per scenario: exit code per variant and where it stops (the RQ1 table)
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
FIXTURES = Path("scenarios/fixtures")
BIN = Path(sys.executable).parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")
MODES = ("basic", "structural", "full")

MANIFEST = Path("scenarios/scenarios.yml")
COLUMNS = ("off", "lint", *MODES)  # variants with a column of their own in the matrix


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


def shown_exit(o: dict) -> str:
    return str(o["exit"]) if o["exit"] == o["expected_exit"] else f"{o['exit']} (expected {o['expected_exit']})"


def matrix_row(sc: dict, outcomes: dict) -> dict:
    """One scenario: observed exit code per variant, '' where the variant is not run."""
    return {
        "id": sc["id"],
        "fault": sc["fault"],
        **{v: shown_exit(outcomes[v]) if v in outcomes else "" for v in COLUMNS},
        "other": "; ".join(f"{n}: {shown_exit(o)}" for n, o in outcomes.items() if n not in COLUMNS),
        "stops": sc["stops"],
    }


def matrix_md(rows: list[dict]) -> str:
    """The matrix as a Markdown table; in fault scenarios the earliest detecting variant is bold."""
    head = ["ID", "Injected fault", *(f"`{v}`" for v in COLUMNS), "Other variants", "Where it stops"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        cells = {v: r[v] for v in COLUMNS}
        if r["id"].startswith("F"):
            first = next((v for v in COLUMNS[1:] if cells[v] == "1"), None)
            if first:
                cells[first] = f"**{cells[first]}**"
        lines.append("| " + " | ".join([r["id"], r["fault"], *cells.values(), r["other"], r["stops"]]) + " |")
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--format-service-url", default=os.environ.get("SOS_FFS_URL", "http://localhost:8000"))
    ap.add_argument("--service-image", default="", help="image (digest) of the service, recorded in env.txt")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--only", default=None, help="comma-separated scenario IDs")
    ap.add_argument("--out", type=Path, default=ROOT / "scenarios" / "results")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    service = ["--format-service-url", a.format_service_url]
    runner, lint = str(BIN / "cwl-format-aware-runner"), str(BIN / "cwl-format-lint")
    has_docker = docker_available()
    a.out.mkdir(parents=True, exist_ok=True)

    plans = []  # (scenario, steps, [(run name, argv without outdir/log, expected exit, uses runner)])
    for sc in YAML(typ="safe").load((ROOT / MANIFEST).read_text()):
        wf = FIXTURES / "workflows" / sc["workflow"]
        files = [str(wf), *([str(FIXTURES / "jobs" / sc["job"])] if sc.get("job") else [])]
        expect = sc["expect"]
        runs = [("off", ["--format-validation", "off", *files], expect["off"], True)] if "off" in expect else []
        runs += [(m, ["--format-validation-mode", m, *files], expect[m], True) for m in MODES if m in expect]
        runs += [(name, [*x["args"], *files], x["exit"], True) for name, x in (sc.get("extra") or {}).items()]
        if "lint" in expect:
            runs.append(("lint", [str(wf)], expect["lint"], False))
        plans.append((sc, steps_of(ROOT / wf), runs))

    problems, summary, matrix = [], [], []
    for sc, steps, runs in plans:
        sid, wf = sc["id"], sc["workflow"]
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
        matrix.append(matrix_row(sc, outcomes))

    if summary:
        write_csv(a.out / "summary.csv", summary)
        write_csv(a.out / "matrix.csv", matrix)
        (a.out / "matrix.md").write_text(matrix_md(matrix))
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
