# RQ1: fault-injection scenarios

RQ1, effectiveness: see [Research Questions](../README.md#research-questions); variants and versions:
[`README.md`](../README.md).

```
run.py          runs the scenarios, verifies their exit codes, writes results/
tables.py       the tables from results/: results/matrix.md (below) and the paper table stats/scenarios.tex
scenarios.yml   the scenarios: fixtures, injected fault, expected exit code per variant
fixtures/       their workflows, tools, jobs and data (make_data.py regenerates the geodata)
results/        the runs reported in the paper
stats/          the paper table
```

## Reproduce

About 15 minutes on any Linux machine with Docker, from the repository root:
```sh
uv sync
docker run -d --name sos-ffs -p 8000:8000 -v "$PWD/mappings:/app/mappings:ro" \
  ghcr.io/dfg-sos/file-format-service-eo-bio:0.4.0
uv run python scenarios/run.py --out /tmp/scenarios
uv run python scenarios/tables.py --results /tmp/scenarios --out /tmp/scenarios/stats   # compare with results/matrix.md
```
The image is the one the results were produced with (digest in `results/env.txt`); to build it from
[`plugins/format-validator-bio`](../plugins/format-validator-bio/Dockerfile) instead:
`docker build -t file-format-service-eo-bio:0.4.0 plugins/format-validator-bio`.
`run.py` exits 1 if any exit code differs from the expected one or between repetitions, `tables.py` if a fault's EO
and Bio scenarios differ in any variant. Scenarios EO-F3.3 and Bio-F3.3 are skipped without a Docker daemon. The
Sympolis scenario (wrong CRS in a real workflow) runs on the cluster with the overhead benchmark; see
[below](#sympolis-wrong-crs-in-a-real-workflow).

## Scenarios

The scenarios are listed in [`scenarios.yml`](scenarios.yml): fixture workflow and job, injected fault and expected exit
code per variant. IDs follow the fault classes of the paper: F1 incompatible formats wired together, F2 wrong workflow
input file, F3 a tool stamps the wrong label on its output, F4 wrong or inapplicable metadata (CRS, geometry type), F5
corrupt file (F5.1 in the metadata, F5.2 in the content); OK are controls (no fault), X limits of the runtime checks. Each scenario belongs to one
application domain: EO (the EO formats ontology) or Bio (EDAM; the runtime checks through the validator plug-in
`plugins/format-validator-bio`). The same ID in both domains is the same fault: Bio F1.1 is EO F1.1 with FASTQ and FASTA
instead of Shapefile and GeoTIFF. F4, F5.1 and X.1 run in EO only: FASTQ has no CRS, geometry type or header metadata,
and X.1 needs an EO format without validator. X.2, an output without format, belongs to no domain (`none`). Results are kept per
`<domain>-<id>`, e.g. `results/Bio-F1.1/`. The fixtures (`fixtures/workflows/`, `tools/`, `jobs/`, `data/`) derive from the runner's `tests/fixtures/`.

[`run.py`](run.py) runs each scenario as `off`, `basic`, `metadata`, `content` (transfer `auto`), and through
`cwl-format-lint`, three times each; [`tables.py`](tables.py) writes the table below as `results/matrix.md`. The runs
use the default policy, `--format-validation fail`: a failed input check stops the step before it runs, a failed output
check fails it after it ran, and the workflow stops. `UNCERTAIN` results only warn and service errors stop the step
(defaults; scenarios X.1 and F4.3 flip them).

## Results

Exit codes (1 = stopped, 0 = completed, empty = not run; bold: the earliest variant that detects the fault). X.2
declares no `$schemas` to lint.

| ID | Domain | Injected fault | `off` | `lint` | `basic` | `metadata` | `content` | Other variants | Where it stops |
|---|---|---|---|---|---|---|---|---|---|
| F1.1 | EO | Shapefile input wired to a GeoTIFF port | 1 | **1** | 1 | 1 | 1 |  | linter: before any job; otherwise cwltool's label check when it creates the `consume` job |
| F1.1 | Bio | FASTQ input wired to a FASTA port | 1 | **1** | 1 | 1 | 1 |  | as F1.1 |
| F1.2 | EO | workflow input declares abstract `eo:Raster` (any raster is valid), wired to a GeoTIFF port: a contract the tool cannot keep; the job passes a valid GeoTIFF | 0 | **1** | 0 | 0 | 0 |  | linter, before any job; cwltool accepts the workflow, and the run completes because the job passes the GeoTIFF that `consume` needs |
| F1.2 | Bio | workflow input declares any sequence format (abstract), wired to a FASTA port: a contract the tool cannot keep; the job passes a valid FASTA | 0 | **1** | 0 | 0 | 0 |  | as F1.2 |
| F1.3 | EO | as F1.2, the job passes a valid NetCDF raster (`eo:NetCDF_CF`), which the `Raster` contract admits | 1 | **1** | 1 | 1 | 1 |  | linter, before any job; cwltool accepts the workflow and the job, and stops at `consume`, whose GeoTIFF port rejects the NetCDF label (tool not run) |
| F1.3 | Bio | as F1.2, the job passes a valid FASTQ (EDAM `format_1930`), which the sequence-format contract admits | 1 | **1** | 1 | 1 | 1 |  | as F1.3 |
| F2.1 | EO | workflow input `roads.geojson` labelled GeoTIFF by the job | 0 | 0 | **1** | 1 | 1 |  | input check of `consume`; `consume` not run |
| F2.1 | Bio | workflow input `reads.fastq` labelled FASTA by the job (validator plug-in) | 0 | 0 | **1** | 1 | 1 |  | input check of `consume`; `consume` not run |
| F2.2 | EO | GeoJSON content named `roads_as.tif`, labelled GeoTIFF | 0 | 0 | 0 | **1** | 1 |  | as F2.1 |
| F2.2 | Bio | FASTQ content named `reads_as.fasta`, labelled FASTA (validator plug-in) | 0 | 0 | 0 | **1** | 1 |  | as F2.1 |
| F2.3 | EO | the job names `missing.tif`, which does not exist | 1 | 0 | **1** | 1 | 1 |  | cwltool, when it loads the job; no step runs |
| F2.3 | Bio | the job names `missing.fasta`, which does not exist | 1 | 0 | **1** | 1 | 1 |  | cwltool, when it loads the job; no step runs |
| F2.4 | EO | a Shapefile without its `.dbf`, which the workflow input requires as a secondary file | 1 | 0 | **1** | 1 | 1 |  | cwltool, when it loads the job; no step runs |
| F3.1 | EO | a tool writes GeoJSON as `out.geojson` and labels it GeoTIFF | 0 | 0 | **1** | 1 | 1 |  | output check of `relabel`; `consume` not run |
| F3.2 | EO | as F3.1, but named `out.tif` | 0 | 0 | 0 | **1** | 1 |  | as F3.1 |
| F3.3 | EO | F3.2 with all steps in `alpine` containers | 0 | 0 | 0 | **1** | 1 |  | as F3.1 |
| F3.1 | Bio | a tool writes FASTQ as `out.fastq` and labels it FASTA (validator plug-in) | 0 | 0 | **1** | 1 | 1 |  | output check of `relabel`; `consume` not run |
| F3.2 | Bio | as F3.1, but named `out.fasta` | 0 | 0 | 0 | **1** | 1 |  | as F3.1 |
| F3.3 | Bio | F3.2 with all steps in `alpine` containers | 0 | 0 | 0 | **1** | 1 |  | as F3.1 |
| F4.1 | EO | GeoTIFF in EPSG:4326, output declares `sos:expectedCRS: EPSG:3857` | 0 | 0 | 0 | **1** | 1 |  | output check of the tool |
| F4.2 | EO | Point GeoJSON, output declares `sos:expectedGeometryType: LineString` | 0 | 0 | 0 | **1** | 1 |  | output check of the tool |
| F4.3 | EO | `sos:expectedGeometryType` on a GeoTIFF output: the service rejects the request in metadata and content mode (`ERROR`, HTTP 400) | 0 | 0 | 0 | **1** | 1 | metadata-service-error-warn: 0 | metadata and content: output check of the tool; the runner treats the rejected request as a service error, so with `--format-service-error warn` it completes with a warning |
| F4.4 | EO | 60 LineStrings, then one Point (GeoJSON), output declares `sos:expectedGeometryType: LineString`: the metadata check samples the first 50 features | 0 | 0 | 0 | 0 | **1** |  | output check of the tool |
| F5.1 | EO | GeoTIFF cut off at 64 bytes, inside its tag directory: size, CRS and pixel layout are missing | 0 | 0 | 0 | **1** | 1 |  | as F2.1 |
| F5.2 | EO | GeoTIFF (64 x 64) cut off halfway: the metadata is intact, the pixel data is not | 0 | 0 | 0 | 0 | **1** |  | as F2.1 |
| F5.2 | Bio | FASTQ cut off inside its second record; FASTQ has no metadata, its first record is intact (validator plug-in) | 0 | 0 | 0 | 0 | **1** |  | as F2.1 |
| OK.1 | EO | none, a valid GeoTIFF into the F2 workflow | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.1 | Bio | none, a valid FASTA into the F2 workflow (validator plug-in) | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.2 | EO | none, Shapefile into an `eo:Vector` port (subclass, multi-file format) | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.2 | Bio | none, FASTA into a port accepting any sequence format (subclass) | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.3 | EO | none, the F4.2 tool with LineStrings | 0 | 0 | 0 | 0 | 0 |  | completes |
| X.1 | EO | output labelled `eo:WKB`, which the service cannot validate: `UNCERTAIN` | 0 | 0 | 0 | 0 | 0 | uncertain-fail: 1 | completes with a warning; with `--format-uncertain fail`: output check of the tool |
| X.2 | none | output without `format`: the runner skips its check and sends nothing to the service | 0 |  | 0 | 0 | 0 |  | completes, not checked (logged as skipped) |

**Findings:**
- **Plain cwltool misses every label and content fault** (F2.1, F2.2, F3–F5; exit 0): it stamps the declared label on outputs and never looks at file content. It stops F1.1 and F1.3 only at runtime, when it creates the `consume` job; the linter rejects their workflows before any job runs.
- **The linter rejects broken format contracts that cwltool accepts** (F1.2, F1.3): a workflow input declared as abstract `eo:Raster` promises that any raster is valid; wiring it to a tool that requires `eo:GeoTIFF` breaks that promise. cwltool accepts the workflow and checks only the labels of the given job: the run completes when the job passes a GeoTIFF (F1.2) and stops at the tool when it passes a NetCDF, a raster the contract admits as well (F1.3). The linter checks the declared formats of the ports and rejects the workflow in both cases, before any job.
- **The wiring checks are not bound to one ontology:** Bio F1.1–F1.3 repeat EO F1.1–F1.3 with EDAM sequence formats, checked against the online `EDAM.owl`, with the same outcome in every variant: FASTQ wired to a FASTA port (F1.1), an abstract sequence-format input wired to a FASTA port, rejected by the linter, completing with a FASTA job (F1.2) and stopped at runtime by a valid FASTQ (F1.3); FASTA into a sequence-format port completes (OK.2, a subclass).
- **The runtime checks extend to another domain without changing the runner or the service** (Bio F2.1–F3.3, F5.2, OK.1): the plug-in `plugins/format-validator-bio` adds FASTA and FASTQ validators (EDAM `format_1929`, `format_1930`), built on Biopython's parsers, to the service image, and its mapping file maps EDAM to them. The unchanged runner v0.2.0 detects a FASTQ file labelled FASTA by its name in `basic` mode (F2.1), FASTQ content named `.fasta` (F2.2) in `metadata` mode, and a FASTQ cut off inside its second record (F5.2) only in `content`, as in EO; the same holds for a tool that labels its FASTQ output FASTA (F3.1–F3.3). Every fault run in both domains has the same outcome in both (`tables.py` checks this).
- **The linter misses all runtime faults** (F2–F5): their labels are consistent, and it does not read jobs. Linter and runner are complementary.
- **`basic` catches wrong extensions** (F2.1, F3.1). **`metadata` catches the rest at a cost independent of the file size:** wrong content behind the right extension (F2.2, F3.2, F3.3), wrong CRS (F4.1), wrong declared geometry type (F4.2) and truncated metadata (F5.1). For FASTA and FASTQ, which carry no metadata, `metadata` parses the first record. **Only `content` catches faults beyond what `metadata` reads:** a geometry of the wrong type after the features `metadata` samples (F4.4) and data cut off behind intact metadata (F5.2). A missing file needs no check of its own, because cwltool never hands one over: it rejects a missing input file (F2.3) and a missing secondary file (F2.4) when it loads the job, in every variant, and missing outputs when it collects them.
- **Detection stops the workflow before the next step:** output faults at the producing step (F3: `consume` not run), input faults before the consuming step (F2, F5).
- **Metadata the format cannot carry is an annotation fault** (F4.3, `sos:expectedGeometryType` on a GeoTIFF): the linter does not check which metadata a format supports, and only `metadata` and `content` send metadata. The service rejects the request (HTTP 400), which the runner reports as `ERROR`, like an unreachable service: it stops the workflow by default, but only warns with `--format-service-error warn`.
- **No false positives** in the controls (OK). **Limits:** a format without validator gives `UNCERTAIN`, which only warns or stops as the policy says (X.1). A port without `format` is skipped and never sent to the service (X.2): the checks cover only what the workflow declares, and workflows without annotations run unchanged.

**Verification:** every run's exit code matched the expected one, and exit code, failed and skipped checks and steps
run were identical in all three repetitions (`run.py` checks both).

### Sympolis: wrong CRS in a real workflow

Not in `run.py`: the fixture steps take milliseconds, so they cannot show the time saved; this scenario does. It
runs on the cluster as the `crs` set of the overhead benchmark (setup, runs and environment:
[`bench/README.md`](../bench/README.md), results in `bench/results/crs/`). `Kahama.gpkg` (68 MB) is reprojected from
EPSG:4326 to EPSG:32736 (UTM 36S), and all 27 vector ports of Sympolis declare `sos:expectedCRS: "EPSG:4326"`
(Sympolis itself declares no CRS; this is the only change).

- **Plain cwltool and `basic` miss it:** the UTM run completes with exit 0 in 120.2 s (median of 10), but yields 2863
  settlement clusters instead of 1106: the result changes silently.
- **`metadata` and `content` stop it at the first check,** the input `vectorFile` of `split`, after 2.64 s with `local`
  and 2.80 s with `upload` (median of 10; cwltool start-up plus one check, which takes 19 ms with `local`). `content`
  stops as early as `metadata`, because it checks the CRS before it reads the features.
- **No false positive:** on the original EPSG:4326 input (`crs-control`), `metadata` passes all 899 checks, and the
  run takes 137.1 s against 134.3 s for `off`.

A wrong CRS therefore stops the workflow before its first step and saves almost the whole execution time.

## Raw results

`results/<domain>-<id>/`: `command.txt` (exact commands), `<variant>.log` (console output of the first repetition), `outcome.json` (expected and observed exit codes per repetition, failed checks with message, skipped checks, steps not run, wall time); plus `summary.csv` (one row per scenario and variant), `env.txt`, and from `tables.py` `matrix.csv` and `matrix.md` (the table above).

`stats/scenarios.csv` and `.tex` (booktabs): the paper table, one row per fault ID with its short label (`label` in `scenarios.yml`), the domains it ran in, stopped ($\bullet$) or completed ($\circ$) per variant, and where it stops (`at`).

**In the paper:** `stats/scenarios.tex`, and one console excerpt, e.g. EO F4.1:
`[step copy_expect_crs.cwl] output 'raster' file 'out.tif' is not valid …#GeoTIFF: FAILURE: File CRS'EPSG:4326' does not match expected CRS 'EPSG:3857'.`

## Environment

Not on the cluster (no timing involved). A laptop (Linux 7.0, Python 3.12.13, Docker 29.5.3). The service runs with
Docker on `localhost:8000` with the mappings in `mappings/` (EO formats, EDAM); image and versions:
[`README.md`](../README.md#versions). `results/env.txt` records the image digest.

Timings in `results/` are wall times of single runs on a laptop with the `fail` policy; do not compare them with the
overhead runs.
