# Benchmark on an HPC node

[`bench.sh`](bench.sh) runs the overhead sets on one exclusively allocated Slurm node. The format service
runs in Apptainer next to cwltool, and both share node-local scratch, so `local` transfer works.
What the runs measure: see [`bench/README.md`](../README.md). `SETS` selects the sets:

| Set | Paper | Result directories |
|---|---|---|
| `sympolis` | RQ2(a) | `rq1-sympolis` |
| `concrete` | RQ2(b) | `rq2-<format>-<N>MB-concrete` |
| `abstract` | RQ2(c) | `rq3-<format>-<N>MB-abstract` |
| `crs` | RQ1, the Sympolis CRS scenario (fault detection), timed in the setup of RQ2(a) | `crs-utm`, `crs-control` |

The result directories keep the repository's original numbering (`rq1`–`rq3`), which the analysis scripts read.

## Requirements
- Slurm, Apptainer (`module load apptainer`; the script tries it, and also `module load squashfs`)
- `uv` on the `PATH` ([install](https://docs.astral.sh/uv/getting-started/installation/)) and `git`
- internet access for `prepare` only. The runs make no network calls.
- node-local scratch (`$TMPDIR`, or set `BENCH_WORK`) with ~15 GB free for the 1000 MB inputs, plus ~1.5 GB for the
  local copies below

Every job first copies what the runs read to `$BENCH_WORK/local`: the service and workflow images, the ontologies,
Node.js, and the Python interpreter, with the environment rebuilt offline from the uv cache (the same `uv.lock`). The
runs also write their timing and service logs there, and each set is copied to the results after it finishes. The
shared home file system stalled for seconds at times, on several nodes in the same second, which otherwise lands in
the measured times. `env.txt` records the interpreter and Node.js that ran.

## 1. Prepare (once, on a node with internet: login node or `salloc`)
```sh
cd format-aware-cwl-icsa27-artifact   # the repository root; all commands run from here
bash bench/hpc/bench.sh prepare
```
This sets up the uv environment (Python 3.13), converts the service image (`FFS_IMAGE`, by default
`ghcr.io/dfg-sos/file-format-service-eo-bio:0.4.0`, pinned by digest: file-format-service-eo 0.4.0, i.e. format-validator 0.5.0
with the EO plug-in, plus the validator plug-in for FASTA and FASTQ, built from
[`plugins/format-validator-bio`](../../plugins/format-validator-bio/Dockerfile))
to `ffs.sif`, and downloads the EO formats ontology and EDAM 1.25. To use a local build instead of the registry image:
```sh
docker build -t file-format-service-eo-bio:0.4.0 plugins/format-validator-bio   # on a machine with Docker
docker save file-format-service-eo-bio:0.4.0 -o file-format-service-eo-bio-0.4.0.tar   # copy it to the cluster
FFS_IMAGE=docker-archive://$HOME/file-format-service-eo-bio-0.4.0.tar bash bench/hpc/bench.sh prepare
```
`prepare` also installs Node.js if missing,
clones Sympolis at its release tag (with its own image pinned to that release), and runs Sympolis
once without validation, which pulls its images into the Singularity cache. Everything lands in
`~/ffs-bench` (`BENCH_HOME`). Rerun it after changing `FFS_IMAGE`: a job stops if `ffs.sif` was built from
another image than `FFS_IMAGE` names, so `env.txt` always records the image that ran.

## 2. Smoke test (~15 min)
```sh
SETS="sympolis concrete abstract" SIZES="1" SYMPOLIS_REPEAT=1 CHAIN_REPEAT=1 sbatch -p <partition> bench/hpc/bench.sh
```
Check `ffs-bench-<job>.out` (it should end without "verification failed"), the `verify.txt` files
(`ok`) and the `service-*.log` files in `bench/results/hpc-<job>/`.

## 3. Full run (estimated 2–4 h; the job limit is 24 h)
```sh
sbatch -p <partition> bench/hpc/bench.sh
```
Commit before submitting: `env.txt` records the repository commit, and a dirty tree is marked as such.

The paper's runs were split into separate jobs on identical nodes, all with the default image, in parallel: RQ2(b)
and (c) one job per size (up to ~2.8 h at 1000 MB), RQ2(a) (~3.2 h) and the Sympolis CRS scenario (~1 h):
```sh
for mb in 1 10 100 1000; do SETS="concrete abstract" SIZES=$mb sbatch -p <partition> bench/hpc/bench.sh; done
SETS=sympolis sbatch -p <partition> bench/hpc/bench.sh
SETS=crs sbatch -p <partition> bench/hpc/bench.sh
```
`SETS` runs its sets one after another in one job, so independent sets finish sooner as separate jobs.

The CRS scenario uses the image of RQ2(a), so its times compare with the 134 s of RQ2(a).
It copies the workflow of RQ2(a) (`SYMPOLIS_INPUT`, `SYMPOLIS_DEPTH`), adds `sos:expectedCRS: "EPSG:4326"` to every vector port
of the workflow and its tools ([`bench/crs_scenario.py`](../crs_scenario.py) `annotate`, 27 ports), and reprojects the
input to `CRS_TARGET` (`reproject`, as `ogr2ogr -t_srs`):
- **`crs-utm`:** the reprojected input, all modes, upload and local, `CRS_REPEAT` runs per variant. `metadata` and
  `content` run with policy `fail` (`run.py --expect-stop`) and must stop on a `FAILURE`; `off` and `basic` must
  complete (`basic` does not read the CRS).
  `wall_ms` of the stopping runs is the time until the run stops, `check_ms` the time of the check that stops it.
- **`crs-control`:** the original input, `off` and `metadata`, one run each: `metadata` must complete without a
  `FAILURE`, so there is no false positive at any of the annotated ports.
- **`crs-clusters.txt`:** the number of settlement clusters in the output of each completed first repetition
  (the outputs themselves are deleted).

| Setting | Default | |
|---|---|---|
| `SETS` | `sympolis concrete abstract crs` | which sets to run, in this order |
| `SIZES` | `1 10 100 1000` | copy-chain input sizes in MB (`concrete`, `abstract`) |
| `FORMATS` | `geotiff geopackage fastq` | copy-chain formats; `shapefile` is also available |
| `CHAIN_REPEAT` | `10` | measured runs per variant of `concrete` and `abstract` |
| `SYMPOLIS_REPEAT` | `10` | measured runs per variant of `sympolis` |
| `SYMPOLIS_INPUT` / `SYMPOLIS_DEPTH` | `Kahama.gpkg` / `2` | GeoPackage in Sympolis' `data/input/` (`Kahama_Small.gpkg` for a quick check); `partitionDepth`, 4^depth tiles in parallel |
| `CRS_REPEAT` | `10` | measured runs per variant of `crs-utm` |
| `CRS_TARGET` | `EPSG:32736` | CRS of the reprojected input (WGS 84 / UTM 36S, the zone of Kahama) |
| `WARMUP` | `1` | unrecorded repetitions per set |
| `ABSTRACT_TRANSFERS` | `local` | transfers of `abstract` |
| `NUMA_NODES` | `4` | abort unless the node has this many NUMA nodes (all reported runs had 4; some HPDA2 nodes have 2 and measure slower); empty to skip |
| `BENCH_HOME` | `~/ffs-bench` | images, ontology, Node.js, Sympolis |
| `BENCH_WORK` | `$TMPDIR/ffs-bench-<job>` | scratch shared with the service; deleted afterwards unless set explicitly |
| `FFS_IMAGE` | `docker://ghcr.io/dfg-sos/file-format-service-eo-bio@sha256:b52a7190…` | service image, anything `apptainer build` accepts |
| `PORT` | `8000` | service port on 127.0.0.1 |

Set them in front of `sbatch`; Slurm passes the environment on. The settings before the sets were named
(`RQS`, `RQ1_*`, `RQ2_REPEAT`, `RQ3_TRANSFERS`) stop the job with a hint to the new name.

## Results
`bench/results/hpc-<job>/`:
- **One directory per set** (`rq1-sympolis`, `rq2-<format>-<N>MB-concrete`,
  `rq3-<format>-<N>MB-abstract`, `crs-utm`, `crs-control`), holding `runs.csv`, `timing.jsonl` and `verify.txt`.
- **`all_runs.csv`:** all `runs.csv` combined, with the set name as first column.
- **`service-<set>.log`:** the service is restarted for every set.
- **`crs-annotate.txt`, `crs-clusters.txt`:** the annotated ports and reprojection, the cluster counts (`crs`).
- **`env.txt`:** node, CPU, memory, versions, and checksums of the images and the ontology.

## Troubleshooting
- **"run 'bash bench/hpc/bench.sh prepare' first":** the service image, the ontology or the
  Sympolis copy is missing in `BENCH_HOME`.
- **The job stops right after the start, in `uv sync`:** the environment is rebuilt offline from the uv cache; run
  `prepare` (or `uv sync --frozen`) once with internet access to fill it.
- **"ffs.sif was not built from …":** `FFS_IMAGE` changed since `prepare`; rerun it, or use the `BENCH_HOME` prepared
  for that image.
- **"service did not start":** see `service-<set>.log`. Another process may use `PORT`, or the
  Apptainer bind of `BENCH_WORK` failed.
- **`verify.txt` lists runs:** a run failed, missed checks, got `ERROR` results, or used another
  transfer than requested. The stderr of failed runs is in `<set>/<run_id>.stderr`.
- **RQ1 fails at the start:** check that `apptainer` is on the `PATH` (`--singularity`) and that the
  images are in `~/ffs-bench/singularity`.
