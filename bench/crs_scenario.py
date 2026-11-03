"""The Sympolis CRS scenario (RQ1, real workflow): a reprojected input, CRS annotations, cluster counts.

    python bench/crs_scenario.py annotate <sympolis dir> [--crs EPSG:4326]
    python bench/crs_scenario.py reproject <in.gpkg> <out.gpkg> [--crs EPSG:32736]
    python bench/crs_scenario.py count <file.gpkg>...

annotate: adds `sos:expectedCRS` to every vector File port (`eo:GeoPackage`, `eo:Shapefile`) of the
  workflow and its tools, on the line after the port's `format`, so `metadata` and `content` check the
  CRS at the inputs and outputs of every step. Files without the `sos` namespace get it. Idempotent.
reproject: writes the input reprojected to another CRS (as `ogr2ogr -t_srs`), the same features and attributes.
count: prints the feature count of each file (one feature per settlement cluster in Sympolis' output).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

SOS_NS = 'sos: "https://dfg-sos.github.io/ontologies/cwl#"'
FORMAT = re.compile(r"^(?P<indent>[ \t]*)format: eo:(GeoPackage|Shapefile)[ \t]*$")
EO_NS = re.compile(r'^(?P<indent>[ \t]+)eo: "https://dfg-sos.github.io/ontologies/eo-formats#"[ \t]*$', re.M)


def annotate_text(text: str, crs: str) -> tuple[str, int]:
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    added = 0
    for i, line in enumerate(lines):
        out.append(line)
        m = FORMAT.match(line.rstrip("\n"))
        if not m:
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if nxt.strip().startswith("sos:expectedCRS:"):  # already annotated (by an earlier call)
            continue
        out.append(f'{m["indent"]}sos:expectedCRS: "{crs}"\n')
        added += 1
    text = "".join(out)
    if added and SOS_NS not in text:
        text, n = EO_NS.subn(lambda m: f"{m.group(0)}\n{m['indent']}{SOS_NS}", text, count=1)
        if n != 1:
            raise SystemExit("no eo namespace to add the sos namespace next to")
    return text, added


def annotate(sympolis: Path, crs: str) -> None:
    total = 0
    for path in sorted([sympolis / "Sympolis.cwl", *(sympolis / "cwl").glob("*.cwl")]):
        text, added = annotate_text(path.read_text(), crs)
        if added:
            path.write_text(text)
            print(f"{path.relative_to(sympolis)}: {added} port(s)")
        total += added
    print(f"{total} ports annotated with sos:expectedCRS: {crs}")


def reproject(src: Path, dst: Path, crs: str) -> None:
    import fiona
    from fiona.crs import CRS
    from fiona.transform import transform_geom

    with fiona.open(src) as inp:
        schema, src_crs, driver = inp.schema, inp.crs, inp.driver
        with fiona.open(dst, "w", driver=driver, schema=schema, crs=CRS.from_user_input(crs)) as out:
            out.writerecords(
                fiona.Feature(
                    geometry=fiona.Geometry.from_dict(transform_geom(src_crs, crs, f.geometry)),
                    properties=f.properties,
                )
                for f in inp
            )
    print(f"{dst}: {src_crs} -> {crs}")


def count(files: list[Path]) -> None:
    import fiona

    for f in files:
        with fiona.open(f) as src:
            print(f"{f}: {len(src)} features, {src.crs}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("annotate")
    a.add_argument("sympolis", type=Path)
    a.add_argument("--crs", default="EPSG:4326")
    r = sub.add_parser("reproject")
    r.add_argument("src", type=Path)
    r.add_argument("dst", type=Path)
    r.add_argument("--crs", default="EPSG:32736")
    c = sub.add_parser("count")
    c.add_argument("files", type=Path, nargs="+")
    args = ap.parse_args()
    if args.cmd == "annotate":
        annotate(args.sympolis, args.crs)
    elif args.cmd == "reproject":
        reproject(args.src, args.dst, args.crs)
    else:
        count(args.files)


if __name__ == "__main__":
    main()
