"""Tables of the fault-injection scenarios (RQ1), from the results of scenarios/run.py.

    uv run python scenarios/tables.py [--results scenarios/results]

Writes
  <--results>/matrix.csv, .md   the artifact table: one row per scenario (domain and id), the injected fault in
                                full, the observed exit code per variant and where the workflow stops
  stats/scenarios.csv, .tex     the paper table (booktabs): one row per fault id with its short label, the domains it
                                ran in and the outcome per variant
and prints the paper table as Markdown. A fault that ran in both domains takes one row only if both had the same
outcome in every variant; the paper table needs every observed exit code to match the expected one. Otherwise
nothing is written and the exit code is 1.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from ruamel.yaml import YAML

HERE = Path(__file__).resolve().parent
COLUMNS = ("off", "lint", "basic", "structural", "full")  # variants with a column of their own
STOPPED, COMPLETED = "●", "○"  # paper table; Markdown and CSV
TEX = {STOPPED: r"$\bullet$", COMPLETED: r"$\circ$", "": "--"}


def shown_exit(o: dict) -> str:
    return str(o["exit"]) if o["exit"] == o["expected_exit"] else f"{o['exit']} (expected {o['expected_exit']})"


def matrix_row(sc: dict, runs: dict) -> dict:
    """One scenario: observed exit code per variant, '' where the variant is not run."""
    return {
        "id": sc["id"],
        "domain": sc["domain"],
        "fault": sc["fault"],
        **{v: shown_exit(runs[v]) if v in runs else "" for v in COLUMNS},
        "other": "; ".join(f"{n}: {shown_exit(o)}" for n, o in runs.items() if n not in COLUMNS),
        "stops": sc["stops"],
    }


def matrix_md(rows: list[dict]) -> str:
    """The matrix as a Markdown table; in fault scenarios the earliest detecting variant is bold."""
    head = ["ID", "Domain", "Injected fault", *(f"`{v}`" for v in COLUMNS), "Other variants", "Where it stops"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        cells = {v: r[v] for v in COLUMNS}
        if r["id"].startswith("F"):
            first = next((v for v in COLUMNS[1:] if cells[v] == "1"), None)
            if first:
                cells[first] = f"**{cells[first]}**"
        lines.append(
            "| " + " | ".join([r["id"], r["domain"], r["fault"], *cells.values(), r["other"], r["stops"]]) + " |"
        )
    return "\n".join(lines) + "\n"


def paper_rows(scenarios: list[dict], results: dict) -> tuple[list[dict], list[str]]:
    """One row per fault id; the scenarios of an id must agree in label, stop and every variant's exit code."""
    rows, problems, by_id = [], [], {}
    for sc in scenarios:
        by_id.setdefault(sc["id"], []).append(sc)
        runs = results[f"{sc['domain']}-{sc['id']}"]
        problems += [
            f"{sc['domain']}-{sc['id']} {n}: {shown_exit(o)}"
            for n, o in runs.items()
            if o["exit"] != o["expected_exit"] or not o["consistent"]
        ]
    for sid, group in by_id.items():
        outcomes = {
            sc["domain"]: (sc["label"], sc["at"], {n: o["exit"] for n, o in results[f"{sc['domain']}-{sid}"].items()})
            for sc in group
        }
        if len({json.dumps(o, sort_keys=True) for o in outcomes.values()}) > 1:
            problems.append(f"{sid}: the domains differ: {outcomes}")
            continue
        label, at, exits = next(iter(outcomes.values()))
        rows.append(
            {
                "id": sid,
                "label": label,
                "domains": ", ".join(outcomes),
                **{v: "" if v not in exits else STOPPED if exits[v] else COMPLETED for v in COLUMNS},
                "at": at,
            }
        )
    return rows, problems


def paper_md(rows: list[dict]) -> str:
    head = ["ID", "Fault", "Domains", *(f"`{v}`" for v in COLUMNS), "Stops at"]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(r.values()) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def paper_tex(rows: list[dict]) -> str:
    """booktabs tabular, a rule between the fault classes (F1, ..., F6, OK, X)."""
    lines = [
        r"\begin{tabular}{lll" + "c" * len(COLUMNS) + "l}",
        r"\toprule",
        "ID & Fault & Domains & " + " & ".join(COLUMNS) + r" & Stops at \\",
        r"\midrule",
    ]
    prev = None
    for r in rows:
        cls = r["id"].split(".")[0]
        if prev and cls != prev:
            lines.append(r"\midrule")
        prev = cls
        cells = [r["id"], r["label"], r["domains"], *(TEX[r[v]] for v in COLUMNS), r["at"]]
        lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, default=HERE / "results")
    ap.add_argument("--out", type=Path, default=HERE / "stats", help="directory of the paper table")
    a = ap.parse_args()
    scenarios = YAML(typ="safe").load((HERE / "scenarios.yml").read_text())
    results, missing = {}, []
    for sc in scenarios:
        key = f"{sc['domain']}-{sc['id']}"
        f = a.results / key / "outcome.json"
        if f.exists():
            results[key] = json.loads(f.read_text())["runs"]
        else:
            missing.append(key)
    if missing:
        print("no results for", ", ".join(missing))
        return 1

    matrix = [matrix_row(sc, results[f"{sc['domain']}-{sc['id']}"]) for sc in scenarios]
    rows, problems = paper_rows(scenarios, results)
    if problems:
        for p in problems:
            print("FAILED:", p)
        return 1
    write_csv(a.results / "matrix.csv", matrix)
    (a.results / "matrix.md").write_text(matrix_md(matrix))
    a.out.mkdir(parents=True, exist_ok=True)
    write_csv(a.out / "scenarios.csv", rows)
    (a.out / "scenarios.tex").write_text(paper_tex(rows))
    print(f"Paper table ({a.out / 'scenarios.tex'}): {STOPPED} stopped, {COMPLETED} completed, empty: not run\n")
    print(paper_md(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
