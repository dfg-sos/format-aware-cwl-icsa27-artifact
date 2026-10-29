"""Draws the overhead figures of the paper from bench/results/ into bench/figures/.

- `validation_latency_by_size.pdf` (RQ2(b), RQ3): copy chains with concrete labels, one panel per format. Client round
  trip per check by file size, mode and transfer; bar = mean of all checks (10 runs x 6 checks), whisker = standard
  deviation. No wall-time overhead: the chains' steps only copy files, so relative overhead says little.
- `validation_latency_sympolis.pdf` (RQ2(a)): Sympolis on Kahama.gpkg. Cumulative validation latency of a run (client
  round trip of all its checks, summed) per variant, next to the cumulative task time of the `off` runs (the tools'
  commands, summed over all steps) for comparison.
  Bar = mean, whisker = standard deviation of the 10 runs. The wall-time increase is a table: sympolis_overhead.py.

    uv run --group plots python bench/plot.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from load_results import load_all

FORMATS = [("geotiff", "GeoTIFF"), ("shapefile", "Shapefile"), ("geopackage", "GeoPackage")]
SIZES = [1, 10, 100, 1000]

# Okabe-Ito; checked for colour-vision deficiency and contrast against white
COLOR = {"basic": "#0072B2", "structural": "#009E73", "full": "#D55E00"}
STYLE = {  # variant -> (label, colour, line style, marker)
    "basic": ("basic", COLOR["basic"], "-", "^"),
    "structural-local": ("structural, local", COLOR["structural"], "-", "o"),
    "structural-upload": ("structural, upload", COLOR["structural"], "--", "s"),
    "full-local": ("full, local", COLOR["full"], "-", "o"),
    "full-upload": ("full, upload", COLOR["full"], "--", "s"),
}
VALIDATED = list(STYLE)

COLUMN, TEXTWIDTH = 3.5, 7.16  # IEEE two-column, inches
INK, MUTED, GRID = "#1A1A1A", "#555555", "#E3E3E3"


def setup() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "TeX Gyre Termes", "Nimbus Roman", "STIXGeneral"],
            "mathtext.fontset": "stix",
            "font.size": 8,
            "axes.titlesize": 8,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": INK,
            "axes.linewidth": 0.6,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.minor.width": 0.4,
            "ytick.minor.width": 0.4,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.5,
            "lines.linewidth": 1.2,
            "lines.markersize": 3.5,
            "hatch.linewidth": 0.6,
            "pdf.fonttype": 42,  # embed TrueType, as IEEE PDF eXpress requires
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
        }
    )


def chain_sets(sets: dict) -> dict:
    return {(rs.format, rs.size_mb): rs for rs in sets.values() if rs.labels == "concrete"}


def variant_bar(ax, x, height, variant: str, **kw) -> None:
    """Bar in the variant's colour: filled for local transfer and basic, hatched for upload."""
    label, color, _, _ = STYLE[variant]
    upload = variant.endswith("upload")
    ax.bar(
        x,
        height,
        color="white" if upload else color,
        edgecolor=color,
        hatch="/////" if upload else None,
        linewidth=0.6,
        label=label,
        **kw,
    )


def plot_validation_latency(sets: dict, out: Path) -> None:
    chains = chain_sets(sets)
    fig, axes = plt.subplots(1, 3, figsize=(TEXTWIDTH, 2.3), sharey=True)
    group = np.arange(len(SIZES))
    step = 0.17  # bar width plus a small gap
    for ax, (fmt, title) in zip(axes, FORMATS, strict=True):
        ax.set_title(title, fontweight="bold")
        for i, variant in enumerate(VALIDATED):
            mean, sd = [], []
            for size in SIZES:
                per_check = np.array([c["duration_ms"] for c in chains[(fmt, size)].variant_checks(variant)])
                mean.append(per_check.mean())
                sd.append(per_check.std(ddof=1))
            mean, sd = np.array(mean), np.array(sd)
            lower = np.minimum(sd, mean * 0.999)  # keep the whisker above 0 on the log axis
            x = group + (i - (len(VALIDATED) - 1) / 2) * step
            variant_bar(
                ax,
                x,
                mean,
                variant,
                width=step * 0.85,
                yerr=[lower, sd],
                error_kw={"elinewidth": 0.6, "capsize": 1.2, "capthick": 0.6, "ecolor": INK},
            )
        ax.set_yscale("log")
        ax.set_ylim(bottom=1)
        ax.set_xticks(group, [f"{s:g}" for s in SIZES])
        ax.tick_params(axis="x", length=0)
        ax.grid(axis="x", visible=False)
        ax.set_xlabel("Input file size (MB)")
    axes[0].set_ylabel("Validation latency per check (ms)")
    axes[0].yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.08))
    fig.tight_layout(w_pad=0.6)
    fig.savefig(out / "validation_latency_by_size.pdf")
    fig.savefig(out / "validation_latency_by_size.png", dpi=300)
    plt.close(fig)


def plot_sympolis(sets: dict, out: Path) -> None:
    rs = sets["rq1-sympolis"]
    # Both sides are summed over parallel work: task time over all steps, latency over all checks. The wall time
    # would understate the work, since Sympolis runs its 16 tiles in parallel.
    off = np.array([r["main_ms"] / 1000 for r in rs.variant_runs("off")])
    fig, ax = plt.subplots(figsize=(COLUMN, 2.1))
    error_kw = {"elinewidth": 0.6, "capsize": 1.5, "capthick": 0.6, "ecolor": INK}
    labels = ["task time\n(off)"]
    ax.bar(
        0, off.mean(), yerr=off.std(ddof=1), width=0.7, color=GRID, edgecolor=MUTED, linewidth=0.6, error_kw=error_kw
    )
    ax.axhline(off.mean(), color=MUTED, lw=0.6, ls=(0, (4, 3)), zorder=1)
    heights = [off.mean()]
    for x, variant in enumerate(VALIDATED, start=1):
        latency = np.array([r["check_ms"] / 1000 for r in rs.variant_runs(variant)])
        variant_bar(ax, x, latency.mean(), variant, width=0.7, yerr=latency.std(ddof=1), error_kw=error_kw)
        labels.append(STYLE[variant][0].replace(", ", "\n"))
        heights.append(latency.mean())
    for x, h in enumerate(heights):
        ax.annotate(
            f"{h:.0f}" if h >= 100 else f"{h:.1f}",
            (x, h),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=6.5,
            color=MUTED,
        )
    ax.set_yscale("log")
    ax.set_ylim(1, 4000)
    ax.yaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax.set_ylabel("Cumulative time per run (s)")
    ax.set_xticks(range(len(labels)), labels)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="x", visible=False)
    fig.savefig(out / "validation_latency_sympolis.pdf")
    fig.savefig(out / "validation_latency_sympolis.png", dpi=300)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=Path(__file__).parent / "figures", type=Path)
    args = p.parse_args()
    args.out.mkdir(exist_ok=True)
    setup()
    sets = load_all()
    plot_validation_latency(sets, args.out)
    plot_sympolis(sets, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
