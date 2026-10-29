# Benchmark on an HPC node

[`bench.sh`](bench.sh) runs RQ1–RQ3 on one exclusively allocated Slurm node. The format service
runs in Apptainer next to cwltool, and both share node-local scratch, so `local` transfer works.
What the runs measure: see [`bench/README.md`](../README.md). The script and the result
directories use the repository's original numbering: `rq1-sympolis` is the paper's RQ2(a), `rq2-*-concrete` is
RQ2(b), and `rq3-*-abstract` is RQ2(c); `RQS="1 2 3"` selects them in that order.

## Requirements
- Slurm, Apptainer (`module load apptainer`; the script tries it, and also `module load squashfs`)
- `uv` on the `PATH` ([install](https://docs.astral.sh/uv/getting-started/installation/)) and `git`
- internet access for `prepare` only. The runs make no network calls.
- node-local scratch (`$TMPDIR`, or set `BENCH_WORK`) with ~15 GB free for the 1000 MB inputs

## 1. Prepare (once, on a node with internet: login node or `salloc`)
```sh
cd format-aware-cwl-icsa27-artifact   # the repository root; all commands run from here
bash bench/hpc/bench.sh prepare
```
This sets up the uv environment (Python 3.13), pulls the service image 0.1.0
(format-validator 0.2.3), and downloads the EO formats ontology. It installs Node.js if missing,
clones Sympolis at its release tag (with its own image pinned to that release), and runs Sympolis
once without validation, which pulls its images into the Singularity cache. Everything lands in
`~/ffs-bench` (`BENCH_HOME`). Rerun it after changing `FFS_IMAGE`.

## 2. Smoke test (~15 min)
```sh
RQS="1 2 3" SIZES="1" RQ1_REPEAT=1 RQ2_REPEAT=1 sbatch -p <partition> bench/hpc/bench.sh
```
Check `ffs-bench-<job>.out` (it should end without "verification failed"), the `verify.txt` files
(`ok`) and the `service-*.log` files in `bench/results/hpc-<job>/`.

## 3. Full run (estimated 2–4 h; the job limit is 24 h)
```sh
sbatch -p <partition> bench/hpc/bench.sh
```
Commit before submitting: `env.txt` records the repository commit, and a dirty tree is marked as such.

The paper's RQ2(a) ran as a separate job (about 2.5 h) with service 0.2.0; prepare and submit in the same shell:
```sh
export BENCH_HOME=$HOME/ffs-bench-0.2.0 FFS_IMAGE=docker://ghcr.io/dfg-sos/file-format-service:0.2.0
bash bench/hpc/bench.sh prepare
RQS=1 sbatch -p <partition> bench/hpc/bench.sh
```

| Setting | Default | |
|---|---|---|
| `RQS` | `1 2 3` | which RQs to run |
| `SIZES` | `1 10 100 1000` | input sizes in MB (RQ2/RQ3) |
| `RQ1_REPEAT` / `RQ2_REPEAT` | `10` / `10` | measured runs per variant (RQ2_REPEAT also applies to RQ3) |
| `WARMUP` | `1` | unrecorded repetitions per set |
| `RQ3_TRANSFERS` | `local` | transfers for the abstract-format runs |
| `BENCH_HOME` | `~/ffs-bench` | images, ontology, Node.js, Sympolis |
| `BENCH_WORK` | `$TMPDIR/ffs-bench-<job>` | scratch shared with the service; deleted afterwards unless set explicitly |
| `FFS_IMAGE` | `file-format-service:0.1.0` | service image |
| `PORT` | `8000` | service port on 127.0.0.1 |

Set them in front of `sbatch`; Slurm passes the environment on.

## Results
`bench/results/hpc-<job>/`:
- **One directory per set** (`rq1-sympolis`, `rq2-<format>-<N>MB-concrete`,
  `rq3-<format>-<N>MB-abstract`), holding `runs.csv`, `timing.jsonl` and `verify.txt`.
- **`all_runs.csv`:** all `runs.csv` combined, with the set name as first column.
- **`service-<set>.log`:** the service is restarted for every set.
- **`env.txt`:** node, CPU, memory, versions, and checksums of the images and the ontology.

## Troubleshooting
- **"run 'bash bench/hpc/bench.sh prepare' first":** the service image, the ontology or the
  Sympolis copy is missing in `BENCH_HOME`.
- **"service did not start":** see `service-<set>.log`. Another process may use `PORT`, or the
  Apptainer bind of `BENCH_WORK` failed.
- **`verify.txt` lists runs:** a run failed, missed checks, got `ERROR` results, or used another
  transfer than requested. The stderr of failed runs is in `<set>/<run_id>.stderr`.
- **RQ1 fails at the start:** check that `apptainer` is on the `PATH` (`--singularity`) and that the
  images are in `~/ffs-bench/singularity`.
