# RQ1: fault-injection scenarios

Effectiveness: does the integration detect injected format and file property faults at design time and at runtime,
and at which point in the workflow? Variants and shared versions: [`README.md`](../README.md).

```
run.py          runs the scenarios, verifies their exit codes, writes results/
scenarios.yml   the scenarios: fixtures, injected fault, expected exit code per variant
fixtures/       their workflows, tools, jobs and data (make_data.py regenerates the geodata)
results/        the runs reported in the paper
```

## Reproduce

About 5 minutes on any Linux machine with Docker, from the repository root:
```sh
uv sync
docker build -t file-format-service-bio:0.2.0 plugins/format-validator-bio
docker run -d --name sos-ffs -p 8000:8000 -v "$PWD/mappings:/app/mappings:ro" \
  file-format-service-bio:0.2.0
uv run python scenarios/run.py --out /tmp/scenarios   # compare with scenarios/results/matrix.md
```
It exits 1 if any exit code differs from the expected one or between repetitions. Scenario F3.3 is skipped without
a Docker daemon. Scenario F4.2 (wrong CRS on Sympolis) was run by hand; see [below](#f42-wrong-crs-on-sympolis).

## Scenarios

The scenarios are listed in [`scenarios.yml`](scenarios.yml): fixture workflow and job, injected fault and expected
exit code per variant. IDs follow the fault classes of the paper: F1 incompatible formats wired together, F2 wrong
workflow input file, F3 a tool stamps the wrong label on its output, F4 wrong CRS, F5 wrong geometry type, F6 corrupt
file; OK are controls (no fault), X limits of the service. The fixtures (`fixtures/workflows/`, `tools/`, `jobs/`,
`data/`) derive from the runner's `tests/fixtures/`.

[`run.py`](run.py) runs each scenario as `off`, `basic`, `structural`, `full` (transfer `auto`), and through
`cwl-format-lint`, three times each, and writes the table below as `matrix.md`. The runs use the default policy,
`--format-validation fail`: a failed input check stops the step before it runs, a failed output check fails it after
it ran, and the workflow stops. `UNCERTAIN` results only warn and service errors stop the step (defaults; scenarios
X.1 and X.2 flip them).

## Results

Exit codes (1 = stopped, 0 = completed; bold: the earliest variant that detects the fault):

| ID | Injected fault | `off` | `lint` | `basic` | `structural` | `full` | Other variants | Where it stops |
|---|---|---|---|---|---|---|---|---|
| F1.1 | Shapefile input wired to a GeoTIFF port | 1 | **1** | 1 | 1 | 1 |  | linter: before any job; otherwise cwltool's label check when it creates the `consume` job |
| F1.2 | workflow input declares abstract `eo:Raster`, wired to a GeoTIFF port; the job passes a valid GeoTIFF | 0 | **1** | 0 | 0 | 0 |  | linter only, before any job; no runtime variant sees a fault with this job |
| F1.3 | as F1.2, the job passes a valid NetCDF raster (`eo:NetCDF_CF`, a `Raster`) | 1 | **1** | 1 | 1 | 1 |  | as F1.1 |
| F1.4 | F1.1 with EDAM instead of the EO ontology, TIFF wired to a NetCDF port |  | **1** |  |  |  |  | linter |
| F1.5 | F1.2 with EDAM, input accepts any sequence format (abstract), wired to a FASTA port |  | **1** |  |  |  |  | linter |
| F2.1 | workflow input `roads.geojson` labelled GeoTIFF by the job | 0 | 0 | **1** | 1 | 1 |  | input check of `consume`; `consume` not run |
| F2.2 | GeoJSON content named `roads_as.tif`, labelled GeoTIFF | 0 | 0 | 0 | 0 | **1** |  | as F2.1 |
| F2.3 | F2.1 in another domain: `reads.fastq` labelled EDAM FASTA (validator plug-in) | 0 | 0 | **1** | 1 | 1 |  | input check of `consume`; `consume` not run |
| F2.4 | F2.2 in another domain: FASTQ content named `reads_as.fasta`, labelled EDAM FASTA (validator plug-in) | 0 | 0 | 0 | 0 | **1** |  | as F2.3 |
| F3.1 | a tool writes GeoJSON as `out.geojson` and labels it GeoTIFF | 0 | 0 | **1** | 1 | 1 |  | output check of `relabel`; `consume` not run |
| F3.2 | as F3.1, but named `out.tif` | 0 | 0 | 0 | 0 | **1** |  | as F3.1 |
| F3.3 | F3.2 with all steps in `alpine` containers | 0 | 0 | 0 | 0 | **1** |  | as F3.1 |
| F4.1 | GeoTIFF in EPSG:4326, output declares `sos:expectedCRS: EPSG:3857` | 0 | 0 | 0 | 0 | **1** |  | output check of the tool |
| F5.1 | Point GeoJSON, output declares `sos:expectedGeometryType: LineString` | 0 | 0 | 0 | 0 | **1** |  | output check of the tool |
| F6.1 | GeoTIFF truncated at 64 bytes | 0 | 0 | 0 | 0 | **1** |  | as F2.1 |
| F6.2 | FASTA whose last record has no sequence, labelled EDAM FASTA (validator plug-in) | 0 | 0 | 0 | 0 | **1** |  | as F2.3 |
| OK.1 | none, a valid GeoTIFF into the F2 workflow | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.2 | none, Shapefile into an `eo:Vector` port (subclass, multi-file format) | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.3 | none, the F5.1 tool with LineStrings | 0 | 0 | 0 | 0 | 0 |  | completes |
| OK.4 | none, unannotated output (skipped, not sent to the service) | 0 |  | 0 | 0 | 0 |  | completes |
| OK.5 | none, EDAM, FASTA into a port accepting any sequence format (subclass) |  | 0 |  |  |  |  | completes |
| OK.6 | none, a valid FASTA into the F2.3 workflow (EDAM, validator plug-in) | 0 | 0 | 0 | 0 | 0 |  | completes |
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
- **Detection stops the workflow before the next step:** output faults at the producing step (F3: `consume` not run), input faults before the consuming step (F2, F6.1). All outcomes were identical in the three repetitions, and the EO scenarios had the same outcomes (exit codes, failed checks, steps run) with service 0.1.0 and 0.2.0.
- **No false positives** in the controls (OK). **Limits:** a format without validator gives `UNCERTAIN` (X.1), metadata the format cannot carry an `ERROR` (X.2); both only warn or stop as the policy says.

**Verification:** every run's exit code matched the expected one, and exit code, failed checks and steps run were
identical in all three repetitions (`run.py` checks both).

### F4.2: wrong CRS on Sympolis

Run once, by hand, locally; not in `run.py`. The fixture steps take milliseconds, so they cannot show time saved; this scenario does. `Kahama_Small.gpkg` reprojected (`ogr2ogr -t_srs`) from EPSG:4326 to EPSG:32736 (UTM 36S) or EPSG:3857 runs through plain Sympolis with exit 0 in about 25 s, but yields 13 clusters instead of 3: the result changes silently. With `sos:expectedCRS: "EPSG:4326"` added to the `vectorFile` input of `cwl/FishnetSplit.cwl` (Sympolis declares no CRS; this is the only change), `full` stops the UTM run at the input check of `split`, the first step, after 3.3 s (cwltool start-up plus one check); `basic` does not detect it; the EPSG:4326 control passes.

**Time saved** needs no extra runs: on the cluster, that check (`full`, input of `split`, 68 MB `Kahama.gpkg`) took about 20 ms with `local` and 180 ms with `upload` transfer (RQ2(a) timing log, [`bench/README.md`](../bench/README.md)), while the whole plain run took 132 s (median of `off`). A wrong CRS therefore stops the workflow before its first step and saves almost the whole execution time.

## Raw results

`results/`: per scenario `command.txt` (exact commands), `<variant>.log` (console output of the first repetition), `outcome.json` (expected and observed exit codes per repetition, failed checks with message, steps not run, wall time); plus `matrix.csv` and `matrix.md` (the table above), `summary.csv` (one row per scenario and variant) and `env.txt`.

**In the paper:** the table above, and one console excerpt, e.g. F4.1:
`[step copy_expect_crs.cwl] output 'raster' file 'out.tif' is not valid …#GeoTIFF: FAILURE: File CRS'EPSG:4326' does not match expected CRS 'EPSG:3857'.`

## Environment

Not on the cluster (no timing involved). A laptop (Linux 7.0, Python 3.12.13, Docker 29.5.3), runner v0.1.0. The
service image is `ghcr.io/dfg-sos/file-format-service:0.2.0` (format-validator 0.3.0, which loads validator
plug-ins) extended by `plugins/format-validator-bio` 0.1.0 ([`Dockerfile`](../plugins/format-validator-bio/Dockerfile)),
run with Docker on `localhost:8010` and the mappings in `mappings/` (EO formats, EDAM). The EO scenarios had the same
outcomes with the 0.1.0 image used for RQ2. `results/env.txt` records the image digests.

Timings in `results/` are wall times of single runs on a laptop with the `fail` policy; do not compare them with the
overhead runs.
