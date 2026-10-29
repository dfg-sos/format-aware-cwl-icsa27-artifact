"""Table for RQ2(a): increase of the time to result of Sympolis on Kahama.gpkg per validation variant.

Per variant: time to result, i.e. the wall time of the runner process (mean and standard deviation of the runs),
its increase over the mean `off` run, absolute and relative, and the cumulative validation latency (client round trip
of all checks of a run, summed). The standard deviation of the increase combines the spread of the variant's and of
the `off` runs (sqrt(sd_variant^2 + sd_off^2)), since both means are estimated from the measured runs.
The relative increase and its standard deviation are taken relative to the mean `off` run.
The tables give every value as mean ± standard deviation, rounded once to 0.1. They show the increase in seconds as the
difference of the rounded times, so that the columns add up; it differs from the exact increase (in the CSV) by at most
0.1 s. The relative increase is exact.

Writes `stats/sympolis_overhead.csv`, `stats/sympolis_overhead.tex` (booktabs) and prints a Markdown table.

    uv run python bench/sympolis_overhead.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from load_results import VARIANTS, load_all

LABEL = {
    "off": "off (no validation)",
    "basic": "basic",
    "structural-local": "structural, local",
    "structural-upload": "structural, upload",
    "full-local": "full, local",
    "full-upload": "full, upload",
}


def mean_sd(values: np.ndarray) -> tuple[float, float]:
    return float(values.mean()), float(values.std(ddof=1))


def overhead(sets: dict) -> list[dict]:
    rs = sets["rq1-sympolis"]
    off, off_sd = mean_sd(np.array([r["wall_ms"] / 1000 for r in rs.variant_runs("off")]))
    rows = []
    for variant in VARIANTS:
        runs = rs.variant_runs(variant)
        wall, wall_sd = mean_sd(np.array([r["wall_ms"] / 1000 for r in runs]))
        latency, latency_sd = mean_sd(np.array([r["check_ms"] / 1000 for r in runs]))
        base = variant == "off"
        rows.append(
            {
                "variant": variant,
                "runs": len(runs),
                "checks_per_run": runs[0]["checks"],
                "wall_s": wall,
                "wall_sd_s": wall_sd,
                "increase_s": "" if base else wall - off,
                "increase_sd_s": "" if base else float(np.hypot(wall_sd, off_sd)),
                "increase_pct": "" if base else (wall - off) / off * 100,
                "increase_pct_sd": "" if base else float(np.hypot(wall_sd, off_sd)) / off * 100,
                "validation_latency_s": "" if base else latency,
                "validation_latency_sd_s": "" if base else latency_sd,
            }
        )
    return rows  # unrounded: the CSV keeps 3 decimals, the tables round once, to 1 decimal


def shown(seconds: float) -> float:
    """The value as the tables show it, rounded to 0.1 s."""
    return float(f"{seconds:.1f}")


def cells(row: dict, off_s: float) -> list[str]:
    if row["variant"] == "off":
        return [LABEL["off"], f"{row['wall_s']:.1f} ± {row['wall_sd_s']:.1f}", "--", "--"]
    return [
        LABEL[row["variant"]],
        f"{row['wall_s']:.1f} ± {row['wall_sd_s']:.1f}",
        f"{shown(row['wall_s']) - shown(off_s):.1f} ± {row['increase_sd_s']:.1f}",
        f"{row['increase_pct']:.1f} ± {row['increase_pct_sd']:.1f}",
    ]


HEADER = ["Variant", "Time to result (s)", "Increase (s)", "Increase (%)"]  # each: mean ± standard deviation


def markdown(rows: list[dict]) -> str:
    lines = ["| " + " | ".join(HEADER) + " |", "|---|---:|---:|---:|"]
    lines += ["| " + " | ".join(cells(r, rows[0]["wall_s"])) + " |" for r in rows]
    return "\n".join(lines)


def latex(rows: list[dict]) -> str:
    def tex(c: str) -> str:
        return c.replace("±", r"$\pm$").replace("%", r"\%").replace("--", "---")

    lines = [r"\begin{tabular}{lrrr}", r"\toprule", " & ".join(tex(h) for h in HEADER) + r" \\", r"\midrule"]
    lines += [" & ".join(tex(c) for c in cells(r, rows[0]["wall_s"])) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(lines) + "\n"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=Path(__file__).parent / "stats", type=Path)
    args = p.parse_args()
    args.out.mkdir(exist_ok=True)
    rows = overhead(load_all())
    with (args.out / "sympolis_overhead.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows({k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()} for r in rows)
    (args.out / "sympolis_overhead.tex").write_text(latex(rows))
    print(f"Sympolis on Kahama.gpkg, mean ± standard deviation of {rows[0]['runs']} runs ({args.out}):\n")
    print(markdown(rows))


if __name__ == "__main__":
    main()
