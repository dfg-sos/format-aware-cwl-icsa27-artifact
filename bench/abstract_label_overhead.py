"""Statistics for RQ2(c): abstract (`eo:Raster`, `eo:Vector`, EDAM `format_1919`) vs. concrete format labels on the
copy chains.

For every format, size and validated variant of the abstract sets (`basic`, `structural-local`, `full-local`), compares
the 10 abstract runs with the 10 concrete runs of the same size, which ran on the same node. Per metric (summed
client round trip `check_ms`, service-side `service_validate_ms`, `wall_ms`) it reports the medians, the difference of
the medians (abstract - concrete, absolute and relative) and a 95 % bootstrap interval of that difference (resampling
the runs of both sets independently, fixed seed). Per-check values divide the per-run value by the checks of the run.

Writes `stats/abstract_label_overhead.csv` (one row per format, size, variant and metric) and prints a summary as
Markdown.

    uv run python bench/abstract_label_overhead.py
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from load_results import load_all

METRICS = ["check_ms", "service_validate_ms", "wall_ms"]
FORMATS = ["geotiff", "geopackage", "fastq"]
BOOTSTRAP = 10_000
SEED = 0


def median_diff_ci(a: np.ndarray, b: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """95 % percentile bootstrap interval of median(a) - median(b)."""
    ra = rng.choice(a, size=(BOOTSTRAP, len(a)))
    rb = rng.choice(b, size=(BOOTSTRAP, len(b)))
    diffs = np.median(ra, axis=1) - np.median(rb, axis=1)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi)


def compare(sets: dict) -> list[dict]:
    rng = np.random.default_rng(SEED)
    concrete = {(rs.format, rs.size_mb): rs for rs in sets.values() if rs.labels == "concrete"}
    rows = []
    for ab in sorted(
        (rs for rs in sets.values() if rs.labels == "abstract"),
        key=lambda rs: (FORMATS.index(rs.format), rs.size_mb),
    ):
        co = concrete[(ab.format, ab.size_mb)]
        for variant in dict.fromkeys(r["variant"] for r in ab.runs):
            a_runs, c_runs = ab.variant_runs(variant), co.variant_runs(variant)
            checks = {r["checks"] for r in a_runs + c_runs}
            if len(checks) != 1:
                raise ValueError(f"{ab.name} {variant}: differing check counts {checks}")
            n_checks = checks.pop()
            for metric in METRICS:
                a = np.array([r[metric] for r in a_runs])
                c = np.array([r[metric] for r in c_runs])
                med_a, med_c = float(np.median(a)), float(np.median(c))
                lo, hi = median_diff_ci(a, c, rng)
                rows.append(
                    {
                        "format": ab.format,
                        "size_mb": ab.size_mb,
                        "variant": variant,
                        "metric": metric,
                        "n_abstract": len(a),
                        "n_concrete": len(c),
                        "checks_per_run": n_checks,
                        "median_concrete": round(med_c, 3),
                        "median_abstract": round(med_a, 3),
                        "diff": round(med_a - med_c, 3),
                        "diff_ci_low": round(lo, 3),
                        "diff_ci_high": round(hi, 3),
                        "diff_pct": round((med_a - med_c) / med_c * 100, 2) if med_c else "",
                        "diff_per_check": round((med_a - med_c) / n_checks, 3),
                    }
                )
    return rows


def summary(rows: list[dict]) -> str:
    """Markdown: per format and variant, the range of the differences over the four sizes."""
    lines = [
        "| Format | Variant | Δ service (ms/run) | Δ round trip (ms/run) | Δ round trip (ms/check) | Δ wall (%) |",
        "|---|---|---|---|---|---|",
    ]

    def rng(fmt: str, variant: str, metric: str, key: str, unit: str = "") -> str:
        vals = [r[key] for r in rows if (r["format"], r["variant"], r["metric"]) == (fmt, variant, metric)]
        return f"{min(vals):+.1f} to {max(vals):+.1f}{unit}"

    for fmt in FORMATS:
        for variant in dict.fromkeys(r["variant"] for r in rows if r["format"] == fmt):
            lines.append(
                f"| {fmt} | {variant} | {rng(fmt, variant, 'service_validate_ms', 'diff')} "
                f"| {rng(fmt, variant, 'check_ms', 'diff')} | {rng(fmt, variant, 'check_ms', 'diff_per_check')} "
                f"| {rng(fmt, variant, 'wall_ms', 'diff_pct')} |"
            )
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=Path(__file__).parent / "stats", type=Path)
    args = p.parse_args()
    args.out.mkdir(exist_ok=True)
    rows = compare(load_all())
    path = args.out / "abstract_label_overhead.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"Abstract - concrete, difference of the medians, range over 1-1000 MB ({path}):\n")
    print(summary(rows))


if __name__ == "__main__":
    main()
