"""Reproduce the validation-overhead benchmark with one command.

    uv run python bench/run.py bench/inputs/geotiff_concrete_chain.cwl bench/inputs/geotiff_10MB_concrete.yml

Every repetition is a fresh `cwl-format-aware-runner` process per variant: `off` (baseline, no
service calls), `basic` (sends file paths only, no file transfer), and `metadata`/`content` x transfer
(`--transfers upload,local` compares sending files by path with uploading them; `local` needs
the inputs and `--tmp-outdir-prefix` inside the service's shared dirs). The variants are interleaved,
and `--warmup` repetitions run first without being recorded. Validation uses `warn` so an invalid
file never shortens a run, and checks both inputs and outputs of every step. Options this script
does not know (e.g. `--singularity`, `--tmp-outdir-prefix`) are passed through to cwltool.
Writes to `<--out>/<--name or timestamp>/`:
  timing.jsonl  every run/check/main/skip record (see README)
  runs.csv      one row per run: wall time, exit code, check counts by direction and result, summed
                check, service-side validation and main-command time
After the runs every validated run is verified: it must have exited 0, checked inputs and outputs,
made as many checks as every other validated run, received no FAILURE or ERROR and used the
requested transfer. `--expect-stop metadata,content` (the Sympolis CRS scenario) runs those modes with
`fail` instead, and their runs must have stopped on a FAILURE. Violations are printed and make the
exit code 1.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

RESULTS = ("SUCCESS", "UNCERTAIN", "FAILURE", "ERROR")
FIELDS = [
    "run_id",
    "workflow",
    "job",
    "mode",
    "transfer",
    "rep",
    "wall_ms",
    "exit",
    "checks",
    "checks_pre",
    "checks_post",
    *(r.lower() for r in RESULTS),
    "skips",
    "transfers_used",
    "bytes_checked",
    "check_ms",
    "service_validate_ms",
    "main_ms",
]


def summarize(log: Path) -> dict[str, dict]:
    sums: dict[str, dict] = defaultdict(lambda: defaultdict(float, transfers_used=set()))
    if not log.exists():
        return sums
    for line in log.read_text().splitlines():
        r = json.loads(line)
        s = sums[r["run_id"]]
        if r["record"] == "check":
            s["checks"] += 1
            s[f"checks_{r['direction']}"] += 1
            s[r["result"].lower()] += 1
            s["transfers_used"].add(r["transfer"] or "-")
            s["bytes_checked"] += (r.get("size_bytes") or 0) + (r.get("secondary_size_bytes") or 0)
            s["check_ms"] += r["duration_ms"]
            s["service_validate_ms"] += (r.get("server_timing") or {}).get("validate", 0.0)
        elif r["record"] == "skip":
            s["skips"] += 1
        elif r["record"] == "main":
            s["main_ms"] += r["main_duration_ms"]
    return sums


def verify(rows: list[dict], stop_modes: tuple[str, ...] = ()) -> list[str]:
    """Problems that make a run unfit for the comparison. Runs of `stop_modes` must have stopped on a FAILURE."""
    problems = []
    counts = Counter(r["checks"] for r in rows if r["mode"] not in ("off", *stop_modes))
    expected = counts.most_common(1)[0][0] if counts else 0
    for r in rows:
        bad = []
        if r["mode"] in stop_modes:
            if r["exit"] == 0 or not r["failure"]:
                bad.append(f"did not stop on a FAILURE (exit {r['exit']}, {r['failure']} FAILURE results)")
        else:
            if r["exit"] != 0:
                bad.append(f"exit {r['exit']}")
            if r["mode"] != "off":
                if not (r["checks_pre"] and r["checks_post"]):
                    bad.append(f"inputs/outputs not both checked (pre {r['checks_pre']}, post {r['checks_post']})")
                if r["checks"] != expected:
                    bad.append(f"{r['checks']} checks, other runs {expected}")
                if r["failure"]:
                    bad.append(f"{r['failure']} FAILURE results (see timing.jsonl)")
        if r["mode"] != "off":
            if r["error"]:
                bad.append(f"{r['error']} ERROR results (see timing.jsonl)")
            want = "-" if r["mode"] == "basic" else r["transfer"]
            if want != "auto" and r["transfers_used"] != want:
                bad.append(f"transfer {r['transfers_used']}, requested {want}")
        if bad:
            problems.append(f"{r['run_id']}: " + "; ".join(bad))
    return problems


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("workflow")
    p.add_argument("job", nargs="?")
    p.add_argument("--repeat", type=int, default=10)
    p.add_argument("--warmup", type=int, default=1, help="unrecorded repetitions before measuring")
    p.add_argument("--modes", default="off,basic,metadata,content")
    p.add_argument("--transfers", default="auto", help="comma-separated: auto, local, upload")
    p.add_argument("--out", default="bench/results")
    p.add_argument("--name", help="results subdirectory (default: timestamp)")
    p.add_argument("--service-url", default="http://localhost:8000")
    p.add_argument(
        "--expect-stop",
        default="",
        help="comma-separated modes that run with `fail` and must stop on a FAILURE (an invalid input)",
    )
    p.add_argument(
        "--keep-outputs",
        action="store_true",
        help="keep the workflow outputs of the first measured repetition in <out>/outputs/<run id>/",
    )
    args, cwltool_args = p.parse_known_args()
    stop_modes = tuple(m for m in args.expect_stop.split(",") if m)

    out = Path(args.out) / (args.name or time.strftime("%Y%m%d-%H%M%S"))
    out.mkdir(parents=True)
    log = out / "timing.jsonl"
    variants = [
        (mode, transfer)
        for mode in args.modes.split(",")
        # off has no checks; basic sends no files, so the transfer does not apply
        for transfer in (["-"] if mode in ("off", "basic") else args.transfers.split(","))
    ]
    rows = []
    for rep in range(-args.warmup, args.repeat):
        for mode, transfer in variants:  # interleave variants so drift affects all equally
            run_id = f"{mode}-{transfer}-{rep}" if transfer != "-" else f"{mode}-{rep}"
            cmd = [
                sys.executable,
                "-m",
                "format_aware_cwl.runner",
                "--quiet",
                "--format-service-url",
                args.service_url,
                "--format-run-id",
                run_id,
                "--format-check",
                "both",
            ]
            if mode == "off":
                cmd += ["--format-validation", "off"]
            else:
                policy = "fail" if mode in stop_modes else "warn"
                cmd += ["--format-validation", policy, "--format-validation-mode", mode]
                if transfer != "-":
                    cmd += ["--format-file-transfer", transfer]
            if rep >= 0:
                cmd += ["--format-timing-log", str(log)]
            with tempfile.TemporaryDirectory() as tmp:
                outdir = out / "outputs" / run_id if args.keep_outputs and rep == 0 else Path(tmp)
                cmd += [*cwltool_args, "--outdir", str(outdir), args.workflow, *([args.job] if args.job else [])]
                t0 = time.perf_counter()
                proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
                wall_ms = (time.perf_counter() - t0) * 1000
            if rep >= 0:
                rows.append(
                    {
                        "run_id": run_id,
                        "workflow": Path(args.workflow).name,
                        "job": Path(args.job).name if args.job else "",
                        "mode": mode,
                        "transfer": transfer,
                        "rep": rep,
                        "wall_ms": round(wall_ms, 3),
                        "exit": proc.returncode,
                    }
                )
            if proc.returncode:
                (out / f"{run_id}.stderr").write_text(proc.stderr)
            print(f"{run_id:22} exit={proc.returncode} {wall_ms:9.1f} ms", file=sys.stderr)

    sums = summarize(log)
    for row in rows:
        s = sums[row["run_id"]]
        row.update({k: int(s[k]) for k in ("checks", "checks_pre", "checks_post", "skips", "bytes_checked")})
        row.update({r.lower(): int(s[r.lower()]) for r in RESULTS})
        row["transfers_used"] = "+".join(sorted(s["transfers_used"]))
        row.update({k: round(s[k], 3) for k in ("check_ms", "service_validate_ms", "main_ms")})
    with open(out / "runs.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    problems = verify(rows, stop_modes)
    (out / "verify.txt").write_text("".join(f"{p}\n" for p in problems) or "ok\n")
    for problem in problems:
        print(f"VERIFY {problem}", file=sys.stderr)
    print(out)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
