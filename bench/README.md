# RQ2 and RQ3: overhead

- **RQ2, overhead:** what do the validation modes add, as a function of file size, format label and relative to task
  runtime? (a) Sympolis on Kahama.gpkg; (b) three-step copy chains, concrete formats; (c) the (b) chains with abstract
  formats.
- **RQ3, access path:** how does validating an uploaded file compare with validating a local file on the same host?
  No separate runs: the `upload` and `local` variants of `metadata` and `content` in RQ2(a) and RQ2(b).

Variants and shared versions: [`README.md`](../README.md). How to run it on Slurm: [`hpc/README.md`](hpc/README.md).

```
run.py          one overhead set: runs every variant, writes runs.csv and timing.jsonl, verifies the runs
make_inputs.py  synthetic GeoTIFF / GeoPackage / FASTQ inputs and copy-chain workflows
hpc/            the Slurm script and its README
results/        raw results (CSV, JSONL, console logs, env.txt per job)
```

The script and the result directories use the original numbering: `rq1-sympolis` is RQ2(a), `rq2-*-concrete` is
RQ2(b), and `rq3-*-abstract` is RQ2(c).

| | Measured runs per variant | Variants | Results |
|---|---|---|---|
| RQ2(a) | 10 | all six | `results/sympolis/` |
| RQ2(b) | 10 | all six | `rq2-*` in `results/copy-chain-1MB`, `-10MB`, `-100MB`, `-1000MB` |
| RQ2(c) | 10 | `basic`, `metadata-local`, `content-local`; compared with the RQ2(b) runs of the same size, on the same node | `rq3-*` in the same directories as RQ2(b) |
| RQ3 | as RQ2 | `upload` vs. `local` of RQ2(a) and RQ2(b) | as RQ2 |
| RQ1, CRS scenario | 10 (`crs-utm`), 1 (`crs-control`) | all six; `crs-control`: `off`, `metadata-local` | `results/crs/` |

`bench.sh` writes each Slurm job to `results/hpc-<job>/`; the directories above combine the jobs of one workflow
and keep each job's `env.txt` (as `env-<job>.txt` for further jobs).

All six variants: `off`, `basic`, and `metadata`/`content` × `upload`/`local`. The runs use the `warn` policy
(`--format-validation warn`), so an invalid file never shortens a run.

**CRS scenario (RQ1):** Sympolis with `sos:expectedCRS: "EPSG:4326"` on all 27 vector ports and Kahama.gpkg reprojected
to UTM 36S (`EPSG:32736`), set up as described in [`hpc/README.md`](hpc/README.md). `metadata` and `content` run with
policy `fail` and stop at the first check (input `vectorFile` of step `split`) after 2.71 s (`local`, median; the check
itself takes 19 ms) and 2.88 s (`upload`). Unchecked, the run takes 120.2 s and silently yields 2863 settlement clusters
instead of 1106. On the original input (`crs-control`) `off` takes 134.9 s (RQ2(a): 134.1 s) and `metadata` raises no
`FAILURE` at any of the 899 checks.

## Local check

The paper's numbers come from the HPC runs; absolute timings depend on the machine. A quick check of one copy chain,
against a service started as in [`scenarios/README.md`](../scenarios/README.md#reproduce), the image of the HPC runs:
```sh
uv run bench/make_inputs.py 1
uv run python bench/run.py bench/inputs/geotiff_concrete_chain.cwl bench/inputs/geotiff_1MB_concrete.yml \
  --repeat 2 --transfers upload --out /tmp/overhead
```

## Workloads

### RQ2(a): Sympolis

Sympolis is a CWL workflow for spatial clustering of building footprints, at release
[`v1.2.0`](https://github.com/dfg-sos/sympolis/releases/tag/v1.2.0) (commit `3fec858`):
- **Steps:** 7 top-level steps (split, filter, clustering, visualization, post-filter, two merges) in
  `ghcr.io/descartesresearch/fishnet-apps:2.0.1` and `ghcr.io/dfg-sos/sympolis:1.2.0` containers,
  run with Apptainer (`--singularity`). Steps run concurrently with `--parallel`.
- **Input:** `Kahama.gpkg` (68 MB, 232,521 building MultiPolygons, EPSG:4326).
- **Job:** `jobs/default.yml` with `partitionDepth: 2` (16 tiles processed in parallel), Delaunay graph
  construction (200 m), DBSCAN clustering (200 m, min. 3), `minArea` 1000 m².
- **Changes to the workflow:** the ontology (`$schemas`) is loaded from a local copy, and the Sympolis tools pull
  the release image `sympolis:1.2.0` instead of `sympolis:latest`.
- **Repetitions:** 10 measured runs per variant (6 variants, 60 runs plus warmup).

### RQ2(b), RQ2(c) and RQ3: copy chains

A workflow of three steps, each running `cp` on its input file. Only parameter
references are used, no JavaScript, so Node.js does not inflate the baseline. One chain per format, with synthetic data
(seeded RNG; EPSG:4326 for the EO formats):

| Format | Content | Size of the 1 / 10 / 100 / 1000 MB inputs (bytes, incl. sidecar files) |
|---|---|---|
| GeoTIFF | uncompressed `uint8` noise, 1 band, 256 × 256 tiles | 1,049,082 / 11,077,314 / 104,870,778 / 1,057,159,554 |
| GeoPackage | random-walk LineStrings, 256 vertices each | 1,245,184 / 11,616,256 / 115,261,440 / 1,152,126,976 |
| FASTQ | reads of 150 random bases with random Phred+33 qualities | 1,048,826 / 10,485,818 / 104,857,822 / 1,048,576,132 |

- **Concrete labels (RQ2(b), RQ3):** every port and file is labelled `eo:GeoTIFF`, `eo:GeoPackage` or EDAM
  `format_1930` (FASTQ).
- **Abstract labels (RQ2(c)):** the same data, with every port and file labelled `eo:Raster`, `eo:Vector` or EDAM
  `format_1919` (sequence record format). The service validates a file with an abstract label against every concrete
  subclass whose extension matches, and the file is valid if any of them succeeds. For `eo:Vector` (`.gpkg`) and the
  sequence formats (`.fastq`) one subclass matches, and the abstract label changes the service time per run by at most
  ±4.4 ms in `basic` and `metadata`, within the noise. For `eo:Raster`, five subclasses match a `.tif` (COG, DEM, DSM, DTM, GeoTIFF), and all
  five run to completion before the first success is taken. In `metadata` this adds 37 to 46 ms service time per
  run (6 checks), independent of file size, under 3.2 % of the wall time. In `content` each of the five reads every
  pixel block: the abstract label costs about 4.8 times the concrete one, +69 ms per run at 1 MB and +19.9 s at
  1000 MB (25.0 instead of 5.2 s service time per run; wall time +163 %). Reading the pixels once for all subclasses
  that share the GeoTIFF container would remove this cost. The abstract `content` sets of GeoPackage and FASTQ ran
  up to 0.2 and 1.0 s per run faster at 1000 MB (≤ 1.1 % of the wall time): drift between two sets of CPU-bound
  runs, which the per-set bootstrap interval does not cover, not an effect of the label.
- **Output annotations:** EO outputs declare `sos:expectedCRS: EPSG:4326`, and GeoPackage outputs also declare
  `sos:expectedGeometryType: LineString`. FASTQ outputs declare no metadata.
- **Checks per run:** each validated run makes 6 checks, an input and an output check for each of the 3 steps.

### How RQ3 is derived

RQ3 needs no extra runs. For each size and format, compare `metadata-upload` with `metadata-local` and `content-upload` with `content-local` from the RQ2(a) and RQ2(b) runs. Report the difference in client round trip (`check_ms`) and the service-side time (`service_validate_ms`), so the transfer cost is separated from the validation cost.

## Procedure

- **Interleaving:** the variants are interleaved within each repetition (off, basic, metadata-upload, …),
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

  All measured runs passed verification (1080 for RQ2(b)/(c), 60 for RQ2(a)), and none had an `UNCERTAIN`,
  `FAILURE` or `ERROR` result. A validated Sympolis run makes 899 checks (633 on inputs, 266 on outputs),
  because steps scattered over the 16 tiles check each tile. These checks cover 3957 MB (3,957,211,136 bytes,
  `bytes_checked`), which the `upload` variants send to the service in every run. Every run also skips 264 Files whose port declares
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
  - RQ2(a): one job (node `hpdar07c03s07`).
  - CRS scenario: one later job on the same node (job 14954998).
  - RQ2(b) and RQ2(c), GeoPackage and FASTQ: one job per size, in parallel on four nodes (1 MB `hpdar09c04s01`,
    10 MB `hpdar07c04s02`, 100 MB `hpdar09c02s09`, 1000 MB `hpdar09c03s09`).
  - RQ2(b) and RQ2(c), GeoTIFF: one later job per size with tiled inputs (`env-<job>.txt`, `inputs-<job>.txt`),
    on four further nodes (1 MB `hpdar09c02s04`, 10 MB `hpdar09c03s08`, 100 MB `hpdar12c03s04`, 1000 MB
    `hpdar12c03s06`). The concrete and abstract sets of a format and size always ran in the same job.
  - All nodes have the same hardware.
- **Node:** 2× Intel Xeon Platinum 8380 (2 × 40 cores, 160 threads, max. 2.3 GHz, 4 NUMA nodes), 1 TB RAM,
  SLES 15 SP7 (kernel 6.4.0). The default frequency scaling was left on, and no CPU pinning was used.
- **Storage:** all inputs and cwltool's working and output directories were on node-local NVMe (`/tmp`).
  The same directory was the service's shared directory for `local` transfer.

| Software | Version |
|---|---|
| Python / httpx | 3.13.14 / 0.28.1 |
| Node.js (cwltool's JavaScript engine, RQ2(a) only) | 26.13.0 |
| Apptainer | 1.2.5 |
| file-format-service, RQ2(a) | `ghcr.io/dfg-sos/file-format-service:0.3.0` (`sha256:e93ccf94…`, format-validator 0.4.0), as in RQ1 without the plug-in, run with Apptainer, uvicorn |
| file-format-service, RQ2(b)/(c) | `ghcr.io/dfg-sos/file-format-service-eo-bio@sha256:8152fa23…`, the RQ1 image (0.3.0 plus the plug-in `plugins/format-validator-bio` 0.4.0), run with Apptainer, uvicorn |
| EO formats ontology | eo-formats 1.0.0, local copy (sha256 `7e867b2d…03ed`) |
| EDAM, RQ2(b)/(c) | EDAM 1.25, local copy (sha256 `af29132f…4f48`) |
| Container images (sha256 of the `.sif`) | fishnet-apps 2.0.1 `88ec6e10…3598`; sympolis 1.2.0 `6167ccbe…67d9` |

`env.txt` in each results directory records the full hardware listing, the versions and the checksums.
RQ2(a) mounts only the EO mapping (`mappings/eo-formats.json`): the EDAM mapping needs the
validator plug-in, which the plain 0.3.0 image lacks.

## Notes

- **Synthetic data:** the copy chains isolate the cost of validation. Their steps do almost no work, so
  the relative overhead is an upper bound. The baseline at 1000 MB (≈ 7 s for GeoTIFF and GeoPackage, ≈ 14 s for
  FASTQ) is dominated by cwltool staging and copying the files.
- **`metadata` is independent of the file size:** with `local` transfer a check takes about 6 ms for GeoTIFF,
  15 ms for GeoPackage (GDAL opens the file, reads CRS and samples up to 50 features) and 4 ms for FASTQ (first
  record), from 1 to 1000 MB. Most of it is the round trip; the service itself needs 0.2 to 12 ms.
- **`content` grows linearly with the file size:** it reads every pixel block, feature or record. At 1000 MB a
  `local` check takes 0.86 s for GeoTIFF, 9.8 s for GeoPackage (fiona iterates 1 GB of LineStrings) and 18.7 s for
  FASTQ (Biopython parses every record), so a run of 6 checks grows by 70 %, 761 % and 794 % over the copy chain.
  In Sympolis (68 MB GeoPackage, 899 checks) `content` adds 114 s (+85 %) with `local`, `metadata` 3.6 s (+2.7 %).
  `metadata` is the fast path for every run; `content` pays off for small files or when it runs off the critical path.
- **`upload` adds the transfer:** the files go over HTTP in every check, about 2.2 to 2.4 s per check at 1000 MB
  for every format, the same in `metadata` and `content`. With `local` the service reads the file in place.
- **Upload over loopback:** `upload` runs send the files over loopback on the same node. Over a network,
  upload costs depend on the bandwidth, while `local` costs do not. RQ3 therefore compares the two access paths on one host only.
- **Geometry types in Sympolis:** its ports declare `sos:expectedGeometryType: Polygon`, while Kahama holds
  MultiPolygons. The checks pass because the validator treats single- and multi-part types as compatible.
- **Policy differs from RQ1:** these runs use `warn` so that every run completes; the fault-injection runs use the
  default `fail` so that they stop on an invalid file. Do not compare timings across the two groups.
