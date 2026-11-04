# Artifact: Enforcing File Property Constraints in Scientific Workflows: An Ontology-Driven Architecture (ICSA 2027)

This artifact references the involved software components of our architecture and further provides the scripts, data, and instructions to reproduce our figures and results.

## Architectural Components

| Component | Repository | Version | Role |
|---|---|---|---|
| Format-Aware CWL Runner | [dfg-sos/format-aware-cwl-runner](https://github.com/dfg-sos/format-aware-cwl-runner) | v0.2.0 | Design-time linter (`cwl-format-lint`) and runtime extension of cwltool (`cwl-format-aware-runner`) |
| File Format Service | [dfg-sos/file-format-service](https://github.com/dfg-sos/file-format-service) | v0.4.0 | Service the runner and linter call to check format compatibility and validate files |
| File Format Validator (Base) | [dfg-sos/file-format-validator](https://github.com/dfg-sos/file-format-validator) | v0.5.0 | Validator core; defines no formats, loads validator plug-ins |
| EO Validator Plugin | [dfg-sos/file-format-validator](https://github.com/dfg-sos/file-format-validator) (`plugins/eo`) | 0.1.0 | EO format validators as a plug-in |
| Bioinformatics Validator Plugin | [`plugins/format-validator-bio`](plugins/format-validator-bio/README.md) (this artifact) | 0.4.0 | FASTA/FASTQ validators as a plug-in |
| EO Format & Metadata Ontology | [dfg-sos/ontologies](https://github.com/dfg-sos/ontologies) | 1.0.0 | Format classes and their hierarchy for EO |
| EDAM Ontology | [edamontology/edamontology](https://github.com/edamontology/edamontology) | 1.25 | Format classes for bioinformatics |
| Sympolis Workflow | [dfg-sos/sympolis](https://github.com/dfg-sos/sympolis) | v1.2.0 | EO workflow used in RQ2(a) |


# Evaluation
The evaluation follows the research questions presented in the paper.

## Research Questions
| | Question | Workload | Measured runs per variant | Paper section | Setup and results |
|---|---|---|---|---|---|
| RQ1 | Effectiveness: does the file format service integration detect injected format and file property faults, and at which point in the workflow? | 33 fault-injection scenarios (linter and runner): 20 with EO formats, 12 of them repeated in bioinformatics (EDAM, runtime checks via a validator plug-in), and 1 without any format | 3 (deterministic; repeated to confirm) | Fault Detection | [`scenarios/`](scenarios/README.md) |
| RQ2 | Overhead: what is the overhead of the validation modes in relation to the file size of the input and relative to a workflow's time to result? | (a) Sympolis on Kahama.gpkg; (b) three-step copy chain, concrete formats; (c) the (b) chains with abstract formats | 10 (plus 1 discarded warm-up) | Validation Time by Validation Mode and File Size; Overhead on an EO Workflow | [`bench/`](bench/README.md) |
| RQ3 | Access path: how does the overhead of validating an uploaded file compare with validating a local file on the same host? | no separate runs: the `upload` and `local` variants of `metadata` and `content` in RQ2(a) and RQ2(b) | as RQ2 | Validation Time by Validation Mode and File Size; Overhead on an EO Workflow | [`bench/`](bench/README.md) |

```
scenarios/    RQ1, fault injection: scenarios, fixtures, results (see its README)
bench/        RQ2 and RQ3, overhead: input generation, Slurm script, results (see its README)
mappings/     the format mappings the service needs (EO formats, EDAM), for both
plugins/      format-validator-bio: FASTA/FASTQ validators as a plug-in, and the Dockerfile
              of the service image with the plug-in
```

## Variants

The paper calls these configurations (Table "Injected faults"). Each run is a fresh `cwl-format-aware-runner` process
(cwltool with the format-validation extension), except `lint`:

| Variant | Description |
|---|---|
| `off` | Baseline: plain cwltool, no service calls |
| `lint` | Design-time compatibility check of the workflow definition (`cwl-format-lint`), no run; RQ1 only |
| `basic` | The service checks file names only (extensions, multi-file components); no file content is sent |
| `metadata` | `basic`, plus the service checks that the files exist, opens each file as the declared format and reads its header: CRS and declared geometry type (EO), the first record (FASTA, FASTQ) |
| `content` | `metadata`, plus the service reads every pixel, feature or record of each file and checks that every feature has the expected geometry type |

`metadata` and `content` each run with two file transfers:
- `upload`: the file bytes are sent over HTTP.
- `local`: only the path is sent, and the service reads the file from a directory it shares with cwltool.

Validation runs on the inputs and outputs of every step (`--format-check both`).

## Requirements

- [uv](https://docs.astral.sh/uv/) and Python 3.12 or 3.13; `uv sync` installs the runner from its tag `v0.2.0`
- Docker (RQ1) or Apptainer and Slurm (RQ2), for the service image
- Node.js for cwltool's JavaScript (Sympolis only; `bench.sh prepare` installs it)

## Reproduce

- **RQ1** (about 15 minutes, any Linux machine with Docker): [`scenarios/README.md`](scenarios/README.md#reproduce)
- **RQ2 and RQ3** (2–4 hours on one exclusive HPC node): [`bench/hpc/README.md`](bench/hpc/README.md); a quick local
  check of one copy chain: [`bench/README.md`](bench/README.md#local-check)

## Versions

| Software | Version |
|---|---|
| format-aware-cwl-runner | v0.2.0 (commit `8d2113f`), pinned in `pyproject.toml` and `uv.lock` |
| cwltool / schema-salad / cwl-utils | 3.3.20260925135507 / 8.10.20260825112551 / 0.45 |
| file-format-service | 0.4.0 |
| format-validator / format-validator-eo / format-validator-bio | 0.5.0 / 0.1.0 / 0.4.0 |
| Biopython (in format-validator-bio) | 1.88 |

All experiments run the service from the image `ghcr.io/dfg-sos/file-format-service-eo-bio:0.4.0`
(`sha256:b52a7190…`). We built it from the published service image with the EO validators,
`ghcr.io/dfg-sos/file-format-service-eo:0.4.0`, by adding the bio plug-in
([`Dockerfile`](plugins/format-validator-bio/Dockerfile)).

`env.txt` in each result directory records the runner commit the run used, the service image, the ontology and the
container checksums. Further versions per environment: [`scenarios/README.md`](scenarios/README.md#environment),
[`bench/README.md`](bench/README.md#environment).

**Names:** the paper's `format-aware cwl runner` is the package and repository `format-aware-cwl-runner`; its
commands are `cwl-format-lint` (linter) and `cwl-format-aware-runner` (runner).

## License

MIT, see [LICENSE](LICENSE).
