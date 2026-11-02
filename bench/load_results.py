"""Loads the overhead results in bench/results/ for plot.py and abstract_label_overhead.py.

Each set is a directory `results/hpc-<job>/<name>/` with `runs.csv` (one row per measured run) and `timing.jsonl`
(one `check` record per validated file). Set names: `rq1-sympolis` (RQ2(a)), `rq2-<format>-<size>MB-concrete`
(RQ2(b)) and `rq3-<format>-<size>MB-abstract` (RQ2(c)).
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

RESULTS = Path(__file__).parent / "results"

# variant ids as in run.py: off, basic, metadata-upload, metadata-local, content-upload, content-local
VARIANTS = ["off", "basic", "metadata-local", "metadata-upload", "content-local", "content-upload"]

CHAIN = re.compile(
    r"rq[23]-(?P<format>geotiff|shapefile|geopackage|fastq)-(?P<size>\d+)MB-(?P<labels>concrete|abstract)"
)


@dataclass
class ResultSet:
    name: str
    path: Path
    format: str | None = None  # copy chains only
    size_mb: int | None = None
    labels: str | None = None  # concrete or abstract
    runs: list[dict] = field(default_factory=list)  # rows of runs.csv, numbers parsed
    checks: list[dict] = field(default_factory=list)  # check records of timing.jsonl

    def variant_runs(self, variant: str) -> list[dict]:
        return [r for r in self.runs if r["variant"] == variant]

    def variant_checks(self, variant: str) -> list[dict]:
        return [c for c in self.checks if c["variant"] == variant]


def variant_of(run_id: str) -> str:
    """`content-local-3` -> `content-local`, `basic-0` -> `basic`."""
    return run_id.rsplit("-", 1)[0]


def load_set(path: Path) -> ResultSet:
    rs = ResultSet(name=path.name, path=path)
    if m := CHAIN.fullmatch(path.name):
        rs.format, rs.size_mb, rs.labels = m["format"], int(m["size"]), m["labels"]
    with (path / "runs.csv").open() as fh:
        for row in csv.DictReader(fh):
            for k in ("wall_ms", "check_ms", "service_validate_ms", "main_ms"):
                row[k] = float(row[k])
            for k in ("rep", "exit", "checks"):
                row[k] = int(row[k])
            row["variant"] = variant_of(row["run_id"])
            rs.runs.append(row)
    measured = {r["run_id"] for r in rs.runs}
    with (path / "timing.jsonl").open() as fh:
        for line in fh:
            rec = json.loads(line)
            if rec["record"] == "check" and rec["run_id"] in measured:
                rec["variant"] = variant_of(rec["run_id"])
                rs.checks.append(rec)
    return rs


def load_all(results: Path = RESULTS) -> dict[str, ResultSet]:
    """All result sets by name. Each name occurs in exactly one job directory."""
    sets: dict[str, ResultSet] = {}
    for path in sorted(results.glob("hpc-*/*/runs.csv")):
        rs = load_set(path.parent)
        if rs.name in sets:
            raise ValueError(f"{rs.name} occurs in {sets[rs.name].path} and {rs.path}")
        sets[rs.name] = rs
    return sets
