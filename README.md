# Artifact: format validation in CWL workflows (ICSA 2027)

Scripts, inputs and raw results of the evaluation of
[format-aware-cwl-runner v0.1.0](https://github.com/dfg-sos/format-aware-cwl-runner/releases/tag/v0.1.0), which validates the files of a
CWL workflow against their declared formats with the
[SOS File Format Service 0.1.0](https://github.com/dfg-sos/file-format-service/pkgs/container/file-format-service): a design-time linter
(`cwl-format-lint`) and a runtime extension of cwltool (`cwl-format-aware-runner`).

How every run was set up, with versions and environment: [`EXPERIMENTAL_SETUP.md`](EXPERIMENTAL_SETUP.md).

## Contents

| Paper | Question | Script | Raw results |
|---|---|---|---|
| RQ1 | Effectiveness: which faults are detected, where the workflow stops | `bench/scenarios.py` | `bench/results/scenarios/` |
| RQ2(a) | Overhead on an EO workflow (Sympolis) | `bench/hpc/bench.sh` (`RQS=1`) | `bench/results/hpc-14595369/` |
| RQ2(b) | Overhead by mode and file size (copy chains, concrete formats) | `bench/hpc/bench.sh` (`RQS=2`) | `bench/results/hpc-14595040` … `43/rq2-*` |
| RQ2(c) | Abstract instead of concrete format labels | `bench/hpc/bench.sh` (`RQS=3`) | `bench/results/hpc-14595040` … `43/rq3-*` |
| RQ3 | Upload vs. local file access | none, derived from RQ2(a) and RQ2(b) | as RQ2 |

The scripts and result directories use the original numbering (`rq1`–`rq3`); the table maps it to the paper.
Jobs 14595040–43 are the 1, 10, 100 and 1000 MB sizes.

```
bench/run.py          one overhead set: runs every variant, writes runs.csv and timing.jsonl, verifies the runs
bench/make_inputs.py  synthetic GeoTIFF / Shapefile / GeoPackage inputs and copy-chain workflows
bench/scenarios.py    the fault-injection scenarios (RQ1)
bench/hpc/            the Slurm script for RQ2 and its README
bench/results/        raw results (CSV, JSONL, console logs, env.txt per job)
fixtures/             scenario workflows, jobs and data; mappings/ is the format mapping the service needs
```

## Requirements

- [uv](https://docs.astral.sh/uv/) and Python 3.12 or 3.13; `uv sync` installs the runner from its tag `v0.1.0`
- Docker (RQ1) or Apptainer and Slurm (RQ2), for the service image
  `ghcr.io/dfg-sos/file-format-service:0.1.0` (commit `6e2070f`)
- Node.js for cwltool's JavaScript (Sympolis only; `bench.sh prepare` installs it)

## Reproduce

**RQ1, fault-injection scenarios (about 5 minutes, any Linux machine with Docker):**
```sh
uv sync
docker run -d --name sos-ffs -p 8000:8000 -v "$PWD/fixtures/mappings:/app/mappings:ro" \
  ghcr.io/dfg-sos/file-format-service:0.1.0
uv run python bench/scenarios.py --out /tmp/scenarios   # compare with bench/results/scenarios/summary.csv
```
It exits 1 if any exit code differs from the expected one or between repetitions. Scenario A2-docker is
skipped without a Docker daemon. Scenario K (wrong CRS on Sympolis) was run by hand; the steps are in
`EXPERIMENTAL_SETUP.md`.

**RQ2, overhead (2–4 hours on one exclusive HPC node):** see [`bench/hpc/README.md`](bench/hpc/README.md).
A quick local check of one copy chain, against the service started above:
```sh
uv run bench/make_inputs.py 1
uv run python bench/run.py bench/inputs/geotiff_concrete_chain.cwl bench/inputs/geotiff_1MB_concrete.yml \
  --repeat 2 --transfers upload --out /tmp/overhead
```
Absolute timings depend on the machine; the paper's numbers come from the HPC runs.

## Versions

The runner is pinned to its release tag `v0.1.0` (commit `881ccdd`) in `pyproject.toml` and `uv.lock`. The service is
the image `ghcr.io/dfg-sos/file-format-service:0.1.0` (commit `6e2070f`), the default in `bench/hpc/bench.sh`.
`env.txt` in each result directory records the runner commit the run used, the service image, the ontology and the
container checksums.

## License

MIT, see [LICENSE](LICENSE).
