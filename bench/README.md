# RQ2 and RQ3: overhead

- **RQ2, overhead:** what do the validation modes add, as a function of file size, format label and relative to task
  runtime? (a) Sympolis on Kahama.gpkg; (b) three-step copy chains, concrete formats; (c) the (b) chains with abstract
  formats.
- **RQ3, access path:** how does validating an uploaded file compare with validating a local file on the same host?
  No separate runs: the `upload` and `local` variants of `structural` and `full` in RQ2(a) and RQ2(b).

Variants and shared versions: [`README.md`](../README.md). How to run it on Slurm: [`hpc/README.md`](hpc/README.md).

```
run.py          one overhead set: runs every variant, writes runs.csv and timing.jsonl, verifies the runs
make_inputs.py  synthetic GeoTIFF / Shapefile / GeoPackage inputs and copy-chain workflows
hpc/            the Slurm script and its README
results/        raw results (CSV, JSONL, console logs, env.txt per job)
```

The script and the result directories use the original numbering: `rq1-sympolis` is RQ2(a), `rq2-*-concrete` is
RQ2(b), and `rq3-*-abstract` is RQ2(c).

| | Measured runs per variant | Variants | Results |
|---|---|---|---|
| RQ2(a) | 3 | all six | `results/hpc-14595369/` |
| RQ2(b) | 10 | all six | `results/hpc-14595040` … `43/rq2-*` (1, 10, 100, 1000 MB) |
| RQ2(c) | 10 | `basic`, `structural-local`, `full-local`; compared with the RQ2(b) runs of the same size, on the same node | `results/hpc-14595040` … `43/rq3-*` |
| RQ3 | as RQ2 | `upload` vs. `local` of RQ2(a) and RQ2(b) | as RQ2 |

All six variants: `off`, `basic`, and `structural`/`full` × `upload`/`local`. The runs use the `warn` policy
(`--format-validation warn`), so an invalid file never shortens a run.

## Local check

The paper's numbers come from the HPC runs; absolute timings depend on the machine. A quick check of one copy chain,
against a service started as in [`scenarios/README.md`](../scenarios/README.md#reproduce) (0.2.0 validates EO formats
like 0.1.0; it adds plug-in loading):
```sh
uv run bench/make_inputs.py 1
uv run python bench/run.py bench/inputs/geotiff_concrete_chain.cwl bench/inputs/geotiff_1MB_concrete.yml \
  --repeat 2 --transfers upload --out /tmp/overhead
```

## Workloads

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
- **Verification:** a run only counts if it
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
- **Metrics per run:**
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
- **Node:** 2× Intel Xeon Platinum 8380 (2 × 40 cores, 160 threads, max. 2.3 GHz, 4 NUMA nodes), 1 TB RAM,
  SLES 15 SP7 (kernel 6.4.0). The default frequency scaling was left on, and no CPU pinning was used.
- **Storage:** all inputs and cwltool's working and output directories were on node-local NVMe (`/tmp`).
  The same directory was the service's shared directory for `local` transfer.

| Software | Version |
|---|---|
| Python / httpx | 3.13.14 / 0.28.1 |
| Node.js (cwltool's JavaScript engine) | 26.12.1 |
| Apptainer | 1.2.5 |
| file-format-service | `ghcr.io/dfg-sos/file-format-service:0.1.0` (revision `6e2070f`, format-validator 0.2.3), run with Apptainer, uvicorn |
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
- **Policy differs from RQ1:** these runs use `warn` so that every run completes; the fault-injection runs use the
  default `fail` so that they stop on an invalid file. Do not compare timings across the two groups.
