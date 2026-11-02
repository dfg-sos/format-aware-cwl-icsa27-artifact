"""Write the dummy-workload inputs: data files of roughly the given sizes in MB, copy-chain workflows and job files.

    uv run bench/make_inputs.py 1 10 100
    uv run bench/make_inputs.py --out /scratch/bench/inputs --formats geotiff,fastq 1 1000

Data, shared by both labellings (EO formats in EPSG:4326):
  geotiff_<N>MB.tif     uncompressed uint8 noise
  shapefile_<N>MB.shp   random-walk LineStrings (+ .shx, .dbf, .prj, .cpg; N counts all of them)
  geopackage_<N>MB.gpkg the same LineStrings
  fastq_<N>MB.fastq     reads of 150 random bases with random Phred+33 qualities
Workflows, one per format and labelling (`concrete`: eo:GeoTIFF / eo:Shapefile / eo:GeoPackage / EDAM FASTQ
(format_1930) on every port and file; `abstract`: eo:Raster / eo:Vector / EDAM sequence record format
(format_1919)):
  <format>_<label>_chain.cwl  three steps, each copying its input (tool: <format>_<label>_copy.cwl)
  <format>_<N>MB_<label>.yml  job file
`--schema` and `--edam-schema` point the workflows' $schemas at other copies of the EO formats ontology and of
EDAM (e.g. local file:// URIs), so runs do not depend on the network.

numpy, rasterio and fiona are dependencies of this artifact (`uv sync`); fiona needs Python < 3.14.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

EO = "https://dfg-sos.github.io/ontologies/eo-formats#"
EDAM = "http://edamontology.org/"
VERTICES = 256  # per LineString; about 4 KiB per feature in either vector format
ORIGIN = (9.0, 50.0)
READ_LENGTH = 150  # bases per FASTQ read

# format -> (extension, ontology, concrete class, abstract class, secondaryFiles patterns)
FORMATS = {
    "geotiff": ("tif", "eo", "GeoTIFF", "Raster", []),
    "shapefile": ("shp", "eo", "Shapefile", "Vector", ["^.shx", "^.dbf", "^.prj", "^.cpg?"]),
    "geopackage": ("gpkg", "eo", "GeoPackage", "Vector", []),
    "fastq": ("fastq", "edam", "format_1930", "format_1919", []),
}
DRIVERS = {"shapefile": "ESRI Shapefile", "geopackage": "GPKG"}
NAMESPACES = {"eo": EO, "edam": EDAM}

ONTOLOGY = "https://dfg-sos.github.io/ontologies/eo-formats.owl"
EDAM_ONTOLOGY = "http://edamontology.org/EDAM_1.25.owl"
HEADERS = {
    "eo": """cwlVersion: v1.2
$namespaces: {eo: "https://dfg-sos.github.io/ontologies/eo-formats#", sos: "https://dfg-sos.github.io/ontologies/cwl#"}
$schemas: [ONTOLOGY]
""",
    "edam": """cwlVersion: v1.2
$namespaces: {edam: "http://edamontology.org/"}
$schemas: [ONTOLOGY]
""",
}

# Copies the primary file and its secondaryFiles to out.<ext> (keeping each file's extension).
# Parameter references only: JavaScript would start Node.js and inflate the baseline.
TOOL = """class: CommandLineTool
baseCommand: [sh, -c, 'for f in "$@"; do cp "$f" "out.${{f##*.}}"; done', copy]
arguments: [$(inputs.src.path){secondary_args}]
inputs:
  src: {{type: File, format: {ns}:{cls}{secondary}}}
outputs:
  out:
    type: File
    format: {ns}:{cls}{metadata}{secondary_out}
    outputBinding: {{glob: out.{ext}}}
"""

WORKFLOW_DOC = "# Dummy workload: three steps passing a {cls}-labelled {fmt} along (each step copies its input).\n"
WORKFLOW = """class: Workflow
inputs:
  src: {{type: File, format: {ns}:{cls}{secondary}}}
outputs:
  result: {{type: File, outputSource: s3/out}}
steps:
  s1: {{run: {tool}, in: {{src: src}}, out: [out]}}
  s2: {{run: {tool}, in: {{src: s1/out}}, out: [out]}}
  s3: {{run: {tool}, in: {{src: s2/out}}, out: [out]}}
"""


def write_raster(path: Path, mb: float, rng: np.random.Generator) -> None:
    import rasterio
    from rasterio.transform import from_origin

    side = int(math.sqrt(mb * 1024 * 1024))
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=side,
        height=side,
        count=1,
        dtype="uint8",
        crs="EPSG:4326",
        transform=from_origin(*ORIGIN, 1e-4, 1e-4),
    ) as dst:
        dst.write(rng.integers(0, 255, (1, side, side), dtype="uint8"))


def write_vector(path: Path, driver: str, mb: float, rng: np.random.Generator) -> None:
    import fiona

    n = max(1, int(mb * 1024 * 1024 / (16 * VERTICES + 150)))
    schema = {"geometry": "LineString", "properties": {"name": "str:16"}}
    with fiona.open(path, "w", driver=driver, crs="EPSG:4326", schema=schema) as dst:
        for start in range(0, n, 1000):
            count = min(1000, n - start)
            steps = rng.normal(0, 1e-4, (count, VERTICES, 2))
            walks = np.cumsum(steps, axis=1) + rng.uniform(0, 1, (count, 1, 2)) + ORIGIN
            dst.writerecords(
                {
                    "geometry": {"type": "LineString", "coordinates": w.tolist()},
                    "properties": {"name": f"f{start + i}"},
                }
                for i, w in enumerate(walks)
            )


def write_fastq(path: Path, mb: float, rng: np.random.Generator) -> None:
    bases = np.frombuffer(b"ACGT", dtype="uint8")
    target, size, n = mb * 1024 * 1024, 0, 0
    with open(path, "wb") as f:
        while size < target:
            count = min(10000, math.ceil((target - size) / (2 * READ_LENGTH + 16)))  # 16: header and line ends
            seqs = bases[rng.integers(0, 4, (count, READ_LENGTH))]
            quals = rng.integers(33, 74, (count, READ_LENGTH), dtype="uint8")  # Phred 0-40, Phred+33
            block = b"".join(
                b"@r%d\n%b\n+\n%b\n" % (n + i, s.tobytes(), q.tobytes())
                for i, (s, q) in enumerate(zip(seqs, quals, strict=True))
            )
            f.write(block)
            size += len(block)
            n += count


def data_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.parent.glob(path.stem + ".*") if p.suffix != ".yml")


def write_cwl(out: Path, fmt: str, schema: str) -> None:
    ext, ns, concrete, abstract, secondary = FORMATS[fmt]
    header = HEADERS[ns].replace("ONTOLOGY", schema)
    sec_in = f", secondaryFiles: [{', '.join(secondary)}]" if secondary else ""
    sec_out = f"\n    secondaryFiles: [{', '.join(secondary)}]" if secondary else ""
    # expected metadata for metadata and content mode: CRS of the EO formats, geometry type of the vector formats; none for FASTQ
    metadata = '\n    sos:expectedCRS: "EPSG:4326"' if ns == "eo" else ""
    if ns == "eo" and fmt != "geotiff":
        metadata += '\n    sos:expectedGeometryType: "LineString"'
    for label, cls in (("concrete", concrete), ("abstract", abstract)):
        tool = f"{fmt}_{label}_copy.cwl"
        (out / tool).write_text(
            header
            + TOOL.format(
                ns=ns,
                cls=cls,
                ext=ext,
                secondary=sec_in,
                secondary_out=sec_out,
                secondary_args=", $(inputs.src.secondaryFiles)" if secondary else "",
                metadata=metadata,
            )
        )
        workflow = WORKFLOW.format(tool=tool, ns=ns, cls=cls, secondary=sec_in)
        (out / f"{fmt}_{label}_chain.cwl").write_text(WORKFLOW_DOC.format(cls=cls, fmt=fmt) + header + workflow)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("sizes", nargs="*", type=float, default=[1, 10, 100], help="nominal sizes in MB")
    p.add_argument("--out", type=Path, default=Path(__file__).parent / "inputs")
    p.add_argument("--formats", default=",".join(FORMATS))
    p.add_argument("--schema", default=ONTOLOGY, help="$schemas entry of the EO workflows")
    p.add_argument("--edam-schema", default=EDAM_ONTOLOGY, help="$schemas entry of the EDAM (FASTQ) workflows")
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    for fmt in args.formats.split(","):
        ext, ns, concrete, abstract, _ = FORMATS[fmt]
        write_cwl(args.out, fmt, args.edam_schema if ns == "edam" else args.schema)
        for mb in args.sizes:
            path = args.out / f"{fmt}_{mb:g}MB.{ext}"
            if not path.exists():
                if fmt == "geotiff":
                    write_raster(path, mb, rng)
                elif fmt == "fastq":
                    write_fastq(path, mb, rng)
                else:
                    write_vector(path, DRIVERS[fmt], mb, rng)
            for label, cls in (("concrete", concrete), ("abstract", abstract)):
                job = args.out / f"{fmt}_{mb:g}MB_{label}.yml"
                job.write_text(f'src: {{class: File, location: {path.name}, format: "{NAMESPACES[ns]}{cls}"}}\n')
            print(path, data_size(path))


if __name__ == "__main__":
    main()
