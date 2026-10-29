# Artifact: format validation in CWL workflows (ICSA 2027)

Scripts, inputs and raw results of the evaluation of
[format-aware-cwl-runner](https://github.com/dfg-sos/format-aware-cwl-runner/releases/tag/v0.1.0), which validates the files of a
CWL workflow against their declared formats with the
[SOS File Format Service](https://github.com/dfg-sos/file-format-service/pkgs/container/file-format-service): a design-time linter
(`cwl-format-lint`) and a runtime extension of cwltool (`cwl-format-aware-runner`). The evaluation ran in October 2026.

## Research questions

The questions are numbered as in the paper (Section "Evaluation").

| | Question | Workload | Measured runs per variant | Paper section | Setup and results |
|---|---|---|---|---|---|
| RQ1 | Effectiveness: does the integration detect injected format and file property faults at design time and at runtime, and at which point in the workflow? | 25 fault-injection scenarios (linter and runner), 4 of them in bioinformatics (EDAM) via a validator plug-in | 3 (deterministic; repeated to confirm) | Effectiveness | [`scenarios/`](scenarios/README.md) |
| RQ2 | Overhead: what do the validation modes add, as a function of file size, format label and relative to task runtime? | (a) Sympolis on Kahama.gpkg; (b) three-step copy chain, concrete formats; (c) the (b) chains with abstract formats | 10 | Overhead by mode and file size; Overhead on an EO workflow | [`bench/`](bench/README.md) |
| RQ3 | Access path: how does validating an uploaded file compare with validating a local file on the same host? | no separate runs: the `upload` and `local` variants of `structural` and `full` in RQ2(a) and RQ2(b) | as RQ2 | Overhead by mode and file size | [`bench/`](bench/README.md) |

```
scenarios/            RQ1, fault injection
  run.py              runs the scenarios, verifies their exit codes, writes the results
  scenarios.yml       the scenarios: fixtures, injected fault, expected exit code per variant
  fixtures/           their workflows, tools, jobs and data
  results/            per scenario: commands, console logs, outcomes; matrix.md is the RQ1 table
bench/                RQ2 and RQ3, overhead
  run.py              one overhead set: runs every variant, writes runs.csv and timing.jsonl, verifies the runs
  make_inputs.py      synthetic GeoTIFF / Shapefile / GeoPackage inputs and copy-chain workflows
  hpc/                the Slurm script and its README
  results/            raw results (CSV, JSONL, console logs, env.txt per job)
mappings/             the format mappings the service needs (EO formats, EDAM), for both
plugins/              format-validator-bio: FASTA/FASTQ validators as a plug-in, and the Dockerfile
                      of the service image with the plug-in
```

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

Validation runs on the inputs and outputs of every step (`--format-check both`). RQ1 uses the default policy
`--format-validation fail`, so a run stops on an invalid file; RQ2 and RQ3 use `warn`, so every run completes.

## Requirements

- [uv](https://docs.astral.sh/uv/) and Python 3.12 or 3.13; `uv sync` installs the runner from its tag `v0.1.0`
- Docker (RQ1) or Apptainer and Slurm (RQ2), for the service image
- Node.js for cwltool's JavaScript (Sympolis only; `bench.sh prepare` installs it)

## Reproduce

- **RQ1** (about 5 minutes, any Linux machine with Docker): [`scenarios/README.md`](scenarios/README.md#reproduce)
- **RQ2 and RQ3** (2–4 hours on one exclusive HPC node): [`bench/hpc/README.md`](bench/hpc/README.md); a quick local
  check of one copy chain: [`bench/README.md`](bench/README.md#local-check)

## Versions

| Software | Version |
|---|---|
| format-aware-cwl-runner | v0.1.0 (commit `881ccdd`), pinned in `pyproject.toml` and `uv.lock` |
| cwltool / schema-salad / cwl-utils | 3.3.20260925135507 / 8.10.20260825112551 / 0.45 |
| file-format-service, RQ1 | `ghcr.io/dfg-sos/file-format-service:0.2.0` (format-validator 0.3.0) plus the plug-in `plugins/format-validator-bio` 0.1.0, Docker |
| file-format-service, RQ2(a) | `ghcr.io/dfg-sos/file-format-service:0.2.0`, without the plug-in, Apptainer |
| file-format-service, RQ2(b), (c) | `ghcr.io/dfg-sos/file-format-service:0.1.0` (commit `6e2070f`, format-validator 0.2.3), Apptainer; the default in `bench/hpc/bench.sh` |
| Sympolis, RQ2(a) | release `v1.2.0`, image `ghcr.io/dfg-sos/sympolis:1.2.0` |

Neither the runner nor the service was changed for the plug-in; 0.2.0 differs from 0.1.0 in loading plug-ins.
`env.txt` in each result directory records the runner commit the run used, the service image, the ontology and the
container checksums. Further versions per environment: [`scenarios/README.md`](scenarios/README.md#environment),
[`bench/README.md`](bench/README.md#environment).

**Name:** these documents say `cwl-format-aware-runner` for the process and `format-aware-cwl-runner` for the
package. Use one name in the paper (the repository is `format-aware-cwl-runner`).

## License

MIT, see [LICENSE](LICENSE).
