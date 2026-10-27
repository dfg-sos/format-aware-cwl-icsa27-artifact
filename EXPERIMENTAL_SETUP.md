# Experimental setup

How the evaluation of the format-aware CWL runner was run (October 2026). Raw data: `bench/results/hpc-<job>/` (overhead runs) and `bench/results/scenarios/` (fault-injection runs).
How to reproduce it: [`bench/hpc/README.md`](bench/hpc/README.md) (overhead runs) and `uv run python bench/scenarios.py` against a running service (fault-injection runs).

## Research questions

The questions are numbered as in the paper (Section "Evaluation"). The scripts and result directory names use the original numbering: `rq1-sympolis` is RQ2(a) here, `rq2-*-concrete` is RQ2(b), and `rq3-*-abstract` is RQ2(c).

| | Question | Workload | Measured runs per variant | Paper section | Status |
|---|---|---|---|---|---|
| RQ1 | Effectiveness: does the integration detect injected format and file property faults at design time and at runtime, and at which point in the workflow? | 25 fault-injection scenarios (linter and runner), 4 of them in bioinformatics (EDAM) via a validator plug-in | 3 (deterministic; repeated to confirm) | Effectiveness | done |
| RQ2 | Overhead: what do the validation modes add, as a function of file size, format label and relative to task runtime? | (a) Sympolis on Kahama.gpkg; (b) three-step copy chain, concrete formats; (c) the (b) chains with abstract formats | (a) 3; (b), (c) 10 | Overhead by mode and file size; Overhead on an EO workflow | done |
| RQ3 | Access path: how does validating an uploaded file compare with validating a local file on the same host? | no separate runs: the `upload` and `local` variants of `structural` and `full` in RQ2(a) and RQ2(b) | as RQ2 | Overhead by mode and file size | done (analysis only) |

## Variants

Each run is a fresh `cwl-format-aware-runner` process (cwltool with the format-validation extension):

| Variant | Description |
|---|---|
| `off` | Baseline: plain cwltool, no service calls |
| `basic` | The service checks file names only (extensions, multi-file components); no file content is sent |
| `structural` | `basic`, plus the service checks that the files exist |
| `full` | `structural`, plus the service opens each file as the declared format and checks CRS and geometry type |

`structural` and `full` each run with two file transfers:
- `upload`: the file bytes are sent over HTTP.
- `local`: only the path is sent, and the service reads the file from a directory it shares with cwltool.

Validation runs on the inputs and outputs of every step (`--format-check both`).

- **Overhead runs (RQ2, RQ3)** use the `warn` policy (`--format-validation warn`), so an invalid file never shortens a run.
- **Fault-injection runs (RQ1)** use the default policy, `--format-validation fail`: a failed input check stops the step before it runs, a failed output check fails it after it ran, and the workflow stops. `UNCERTAIN` results only warn and service errors stop the step (defaults; scenarios G and H flip them).
- RQ2(a) and RQ2(b) cover all six variants (`off`, `basic`, and `structural`/`full` × `upload`/`local`). RQ2(c) covers `basic`, `structural-local` and `full-local`, and is compared against the RQ2(b) runs of the same size, which ran on the same node.

## Workloads

### RQ1: fault-injection scenarios

The scenarios are listed in [`fixtures/scenarios.yml`](fixtures/scenarios.yml): fixture workflow and job, injected fault and expected exit code per variant. IDs follow the fault classes of the paper: F1 incompatible formats wired together, F2 wrong workflow input file, F3 a tool stamps the wrong label on its output, F4 wrong CRS, F5 wrong geometry type, F6 corrupt file; OK are controls (no fault), X limits of the service. The fixtures (`fixtures/workflows/`, `tools/`, `jobs/`, `data/`) derive from the runner's `tests/fixtures/`. [`bench/scenarios.py`](bench/scenarios.py) runs each scenario as `off`, `basic`, `structural`, `full` (transfer `auto`), and through `cwl-format-lint`, three times each, and writes the table below as `matrix.md`. Exit codes (1 = stopped, 0 = completed; bold: the earliest variant that detects the fault):

| ID | Injected fault | `off` | `lint` | `basic` | `structural` | `full` | Other variants | Where it stops |
|---|---|---|---|---|---|---|---|---|
| F1.1 | Shapefile input wired to a GeoTIFF port | 1 | **1** | 1 | 1 | 1 |  | linter: before any job; otherwise cwltool's label check when it creates the `consume` job |
| F1.2 | workflow input declares abstract `eo:Raster`, wired to a GeoTIFF port; the job passes a valid GeoTIFF | 0 | **1** | 0 | 0 | 0 |  | linter only, before any job; no runtime variant sees a fault with this job |
| F1.3 | as F1.2, the job passes a valid NetCDF raster (`eo:NetCDF_CF`, a `Raster`) | 1 | **1** | 1 | 1 | 1 |  | as F1.1 |
| F1.4 | F1.1 with EDAM instead of the EO ontology, TIFF wired to a NetCDF port |  | **1** |  |  |  |  | linter |
| F1.5 | F1.2 with EDAM, input accepts any sequence format (abstract), wired to a FASTA port |  | **1** |  |  |  |  | linter |
| F2.1 | workflow input `roads.geojson` labelled GeoTIFF by the job | 0 | 0 | **1** | 1 | 1 |  | input check of `consume`; `consume` not run |
| F2.2 | GeoJSON content named `roads_as.tif`, labelled GeoTIFF | 0 | 0 | 0 | 0 | **1** |  | as F2.1 |
| F3.1 | a tool writes GeoJSON as `out.geojson` and labels it GeoTIFF | 0 | 0 | **1** | 1 | 1 |  | output check of `relabel`; `consume` not run |
| F3.2 | as F3.1, but named `out.tif` | 0 | 0 | 0 | 0 | **1** |  | as F3.1 |
| F3.3 | F3.2 with all steps in `alpine` containers | 0 | 0 | 0 | 0 | **1** |  | as F3.1 |
| F4.1 | GeoTIFF in EPSG:4326, output declares `sos:expectedCRS: EPSG:3857` | 0 | 0 | 0 | 0 | **1** |  | output check of the tool |
| F5.1 | Point GeoJSON, output declares `sos:expectedGeometryType: LineString` | 0 | 0 | 0 | 0 | **1** |  | output check of the tool |
| F6.1 | GeoTIFF truncated at 64 bytes | 0 | 0 | 0 | 0 | **1** |  | as F2.1 |
| OK.1 | none, a valid GeoTIFF into the F2 workflow | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.2 | none, Shapefile into an `eo:Vector` port (subclass, multi-file format) | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.3 | none, the F5.1 tool with LineStrings | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.4 | none, unannotated output (skipped, not sent to the service) | 0 |  | 0 | 0 | 0 |  | completes |
| OK.5 | none, EDAM, FASTA into a port accepting any sequence format (subclass) |  | 0 |  |  |  |  | completes |
| X.1 | output labelled `eo:WKB`, which the service cannot validate: `UNCERTAIN` | 0 | 0 | 0 | 0 | 0 | uncertain-fail: 1 | completes with a warning; with `--format-uncertain fail`: output check of the tool |
| X.2 | `sos:expectedGeometryType` on a GeoTIFF: the service rejects the request in full mode (`ERROR`) | 0 | 0 | 0 | 0 | 1 | full-service-error-warn: 0 | full: output check of the tool; with `--format-service-error warn` it completes with a warning |
| X.3 | EO formats checked against EDAM, which does not define them (`unknown-format`) |  | 1 |  |  |  |  | linter |

**Findings:**
- **Plain cwltool misses every runtime fault** (exit 0): it stamps the declared label on outputs and never looks at file content. It catches F1.1 only at runtime, when it creates the `consume` job; the linter catches F1.1 before any job runs.
- **The linter catches latent wiring faults that no run shows** (F1.2): cwltool checks the labels of the files in the given job, the linter the declared formats of the ports. An abstract input format (`eo:Raster`) wired to a concrete port (`eo:GeoTIFF`) passes every runtime variant as long as the job happens to pass a GeoTIFF; the first valid non-GeoTIFF raster stops the workflow (F1.3).
- **The linter is not bound to one ontology:** the same wiring faults are found with EDAM, against the online `EDAM.owl` (F1.4 concrete, F1.5 abstract; OK.5 a compatible subclass). Formats that the given ontology does not define are reported as `unknown-format`, not as incompatible (X.3).
- **The runtime checks extend to another domain without changing the runner or the service** (F2.3, F2.4, F6.2, OK.6): the plug-in `plugins/format-validator-bio` adds FASTA and FASTQ validators (EDAM `format_1929`, `format_1930`) to the service image, and its mapping file maps EDAM to them. The unchanged runner v0.1.0 detects a FASTQ file labelled FASTA by its name in `basic` mode (F2.3), and FASTQ content named `.fasta` (F2.4) and a truncated FASTA (F6.2) only in `full`, as their EO counterparts F2.1, F2.2 and F6.1.
- **The linter misses all runtime faults** (F2–F6): their labels are consistent. Linter and runner are complementary.
- **`basic` catches wrong extensions** (F2.1, F3.1). Wrong content, CRS, geometry type and truncation need `full`. `structural` caught nothing that `basic` missed, because cwltool never hands over a missing file: it rejects missing inputs and secondary files when it starts and missing outputs when it collects them.
- **Detection stops the workflow before the next step:** output faults at the producing step (F3: `consume` not run), input faults before the consuming step (F2, F6.1). All outcomes were identical in the three repetitions.
- **No false positives** in the controls (OK). **Limits:** a format without validator gives `UNCERTAIN` (X.1), metadata the format cannot carry an `ERROR` (X.2); both only warn or stop as the policy says.

**F4.2: wrong CRS on Sympolis** (run once, by hand, locally; not in `bench/scenarios.py`). The fixture steps take milliseconds, so they cannot show time saved; this scenario does. `Kahama_Small.gpkg` reprojected (`ogr2ogr -t_srs`) from EPSG:4326 to EPSG:32736 (UTM 36S) or EPSG:3857 runs through plain Sympolis with exit 0 in about 25 s, but yields 13 clusters instead of 3: the result changes silently. With `sos:expectedCRS: "EPSG:4326"` added to the `vectorFile` input of `cwl/FishnetSplit.cwl` (Sympolis declares no CRS; this is the only change), `full` stops the UTM run at the input check of `split`, the first step, after 3.3 s (cwltool start-up plus one check); `basic` does not detect it; the EPSG:4326 control passes.

**Time saved** needs no extra runs: on the cluster, that check (`full`, input of `split`, 68 MB `Kahama.gpkg`) took about 20 ms with `local` and 180 ms with `upload` transfer (RQ2(a) timing log), while the whole plain run took 132 s (median of `off`). A wrong CRS therefore stops the workflow before its first step and saves almost the whole execution time.

**Artifact** (`bench/results/scenarios/`): per scenario `command.txt` (exact commands), `<variant>.log` (console output of the first repetition), `outcome.json` (expected and observed exit codes per repetition, failed checks with message, steps not run, wall time); plus `matrix.csv` and `matrix.md` (the table above), `summary.csv` (one row per scenario and variant) and `env.txt`.

**In the paper:** the table above, and one console excerpt, e.g. F4.1:
`[step copy_expect_crs.cwl] output 'raster' file 'out.tif' is not valid …#GeoTIFF: FAILURE: File CRS'EPSG:4326' does not match expected CRS 'EPSG:3857'.`

### RQ2(a): Sympolis

Sympolis is a CWL workflow for spatial clustering of building footprints, at commit
[`12c2605`](https://github.com/dfg-sos/sympolis/commit/12c26055990b190fbe7862beed58353d33934c05):
- **Steps:** 7 top-level steps (split, filter, clustering, visualization, post-filter, two merges) in
  `ghcr.io/descartesresearch/fishnet-apps:2.0.1` and `ghcr.io/dfg-sos/sympolis:latest` containers,
  run with Apptainer (`--singularity`). Steps run concurrently with `--parallel`.
- **Input:** `Kahama.gpkg` (68 MB, 232,521 building MultiPolygons, EPSG:4326).
- **Job:** `jobs/default.yml` with `partitionDepth: 2` (16 tiles processed in parallel), Delaunay graph
  construction (200 m), DBSCAN clustering (200 m, min. 3), `minArea` 1000 m².
- **Change to the workflow:** the only change is that the ontology (`$schemas`) is loaded from a local copy.
- **Repetitions:** 3 measured runs per variant (6 variants, 18 runs plus warmup). This is fewer than the 10 used for the copy chains; report the spread, not only the median.

### RQ2(b), RQ2(c) and RQ3: copy chains

A workflow of three steps, each running `cp` on its input file. Only parameter
references are used, no JavaScript, so Node.js does not inflate the baseline. One chain per format, with synthetic data
(seeded RNG, EPSG:4326):

| Format | Content | Size of the 1 / 10 / 100 / 1000 MB inputs (bytes, incl. sidecar files) |
|---|---|---|
| GeoTIFF | uncompressed `uint8` noise, 1 band, untiled | 1,049,710 / 10,494,724 / 104,919,406 / 1,048,723,813 |
| Shapefile | random-walk LineStrings, 256 vertices each (`.shp` + `.shx/.dbf/.prj/.cpg`) | 1,027,963 / 10,313,434 / 103,151,436 / 1,031,535,633 |
| GeoPackage | the same LineStrings | 1,245,184 / 11,616,256 / 115,273,728 / 1,152,102,400 |

- **Concrete labels (RQ2(b), RQ3):** every port and file is labelled `eo:GeoTIFF`, `eo:Shapefile` or `eo:GeoPackage`.
- **Abstract labels (RQ2(c)):** the same data, with every port and file labelled `eo:Raster` or `eo:Vector`.
  Figure: concrete vs. abstract per format and mode. Abstract labels add 1–2 ms service time per run (subclass
  lookup) in every case except `full` on GeoTIFF (`eo:Raster`): +32 to +47 ms service time and +32 to +48 ms round trip
  per run (6 checks), independent of file size; wall time changes by under 3 %.
- **Output annotations:** outputs declare `sos:expectedCRS: EPSG:4326`, and vector outputs also declare
  `sos:expectedGeometryType: LineString`.
- **Checks per run:** each validated run makes 6 checks, an input and an output check for each of the 3 steps.

### How RQ3 is derived

RQ3 needs no extra runs. For each size and format, compare `structural-upload` with `structural-local` and `full-upload` with `full-local` from the RQ2(a) and RQ2(b) runs. Report the difference in client round trip (`check_ms`) and the service-side time (`service_validate_ms`), so the transfer cost is separated from the validation cost.

## Procedure

- **Interleaving:** the variants are interleaved within each repetition (off, basic, structural-upload, …),
  so drift affects all variants equally.
- **Warmup:** each set first runs one unrecorded warmup repetition.
- **Fresh service per set:** the format service is restarted for every set (one workload × format × size),
  so no service state carries over between sets.
- **Verification (overhead runs):** a run only counts if it
  - exited 0,
  - checked both inputs and outputs,
  - made as many checks as every other validated run,
  - received no `ERROR` result, and
  - used the requested transfer.

  All measured runs passed verification (1080 for RQ2(b)/(c), 18 for RQ2(a)), and none had an `UNCERTAIN`,
  `FAILURE` or `ERROR` result. A validated Sympolis run makes 899 checks (633 on inputs, 266 on outputs),
  because steps scattered over the 16 tiles check each tile. Every run also skips 264 Files whose port declares
  no format (`skips`): Sympolis' internal graph files (`.bin`, 206) and workload lists (`.json`, 58), for which
  the ontology has no class. They are not sent to the service.
- **Verification (fault-injection runs):** every run's exit code matched the expected one, and exit code, failed checks and steps run were identical in all three repetitions (`bench/scenarios.py` checks both).
- **Metrics per run (overhead runs):**
  - wall time of the runner process (`wall_ms`)
  - summed client round trip of all checks (`check_ms`)
  - service-side validation time (`service_validate_ms`, from the service's `Server-Timing` header)
  - time of the tools' own commands (`main_ms`)
  - checks per result, bytes checked

## Environment

- **Cluster:** LRZ HPDA2, partition `hpda2_compute`. Each Slurm job ran exclusively (`--exclusive`) on
  one node. The service and cwltool ran on the same node, with the service on `127.0.0.1`.
- **Jobs:**
  - RQ2(a): one job (node `hpdar09c05s03`).
  - RQ2(b) and RQ2(c): one job per size, in parallel on four identical nodes (1 MB `hpdar10c04s11`,
    10 MB `hpdar09c05s01`, 100 MB `hpdar09c05s02`, 1000 MB `hpdar09c05s03`).
  - RQ1: not on the cluster (no timing involved). A laptop (Linux 7.0, Python 3.12.13, Docker 29.5.3), with the service image `ghcr.io/dfg-sos/file-format-service:0.2.0` (format-validator 0.3.0, which loads validator plug-ins) extended by `plugins/format-validator-bio` (`plugins/format-validator-bio/Dockerfile`), run with Docker on `localhost:8010` and the mappings in `fixtures/mappings/` (EO formats, EDAM). Runner v0.1.0. The EO scenarios had the same outcomes with the 0.1.0 image used for RQ2.
- **Node:** 2× Intel Xeon Platinum 8380 (2 × 40 cores, 160 threads, max. 2.3 GHz, 4 NUMA nodes), 1 TB RAM,
  SLES 15 SP7 (kernel 6.4.0). The default frequency scaling was left on, and no CPU pinning was used.
- **Storage:** all inputs and cwltool's working and output directories were on node-local NVMe (`/tmp`).
  The same directory was the service's shared directory for `local` transfer.

| Software | Version |
|---|---|
| format-aware-cwl-runner | v0.1.0 (commit `881ccdd`) |
| cwltool / schema-salad / cwl-utils | 3.3.20260925135507 / 8.10.20260825112551 / 0.45 |
| Python / httpx | 3.13.14 / 0.28.1 |
| Node.js (cwltool's JavaScript engine) | 26.12.1 |
| Apptainer | 1.2.5 |
| file-format-service | RQ2: `ghcr.io/dfg-sos/file-format-service:0.1.0` (revision `6e2070f`, format-validator 0.2.3), run with Apptainer, uvicorn. RQ1: `0.2.0` (format-validator 0.3.0) plus format-validator-bio 0.1.0, Docker |
| EO formats ontology | eo-formats 1.0.0, local copy (sha256 `7e867b2d…03ed`) |
| Container images (sha256 of the `.sif`) | fishnet-apps 2.0.1 `88ec6e10…3598`; sympolis:latest `0d8aeaab…10ae` |

`env.txt` in each results directory records the full hardware listing, the versions and the checksums.
Its service image, `@sha256:8997661d…c291`, is an earlier build of the same revision `6e2070f`, made before the
`0.1.0` tag.

## Notes

- **Synthetic data:** the copy chains isolate the cost of validation. Their steps do almost no work, so
  the relative overhead is an upper bound. The baseline at 1000 MB (≈ 7 s) is dominated by cwltool
  staging and copying the files.
- **Upload over loopback:** `upload` runs send the files over loopback on the same node. Over a network,
  upload costs depend on the bandwidth, while `local` costs do not. RQ3 therefore compares the two access paths on one host only.
- **Mutable image tag:** `sympolis:latest` is a mutable tag. The image used is identified by the checksum above.
- **Geometry types in Sympolis:** its ports declare `sos:expectedGeometryType: Polygon`, while Kahama holds
  MultiPolygons. The checks pass because the validator treats single- and multi-part types as compatible.
- **Policy differs between RQ1 and the overhead runs:** overhead runs use `warn` so that every run completes; the fault-injection runs use the default `fail` so that they stop on an invalid file. Do not compare timings across the two groups.
- **Name:** this document says `cwl-format-aware-runner` for the process and `format-aware-cwl-runner` for the package. Use one name in the paper (the repository is `format-aware-cwl-runner`).
