# format-validator-bio

Demo plugin for [format-validator](https://github.com/dfg-sos/file-format-validator) that adds FASTA ([EDAM format_1929](http://edamontology.org/format_1929)) and FASTQ ([EDAM format_1930](http://edamontology.org/format_1930)) validators without changing the core. It is discovered through the `format_validator.validators` entry point declared in [pyproject.toml](pyproject.toml).

## Why it is in this artifact

The paper claims that the architecture extends to other domains and is ontology-neutral (R2, design decision D2: validators as discovered plug-ins). This package is the evidence: a second domain (bioinformatics, EDAM ontology) added as an ordinary Python package, with **no changes** to the validator core or the service. The EO formats are a plug-in of the same kind (`format-validator-eo`, in the validator's repository). What it took:

| Part | Size |
|---|---|
| Validators (`src/validators.py`, `src/__init__.py`), on [Biopython](https://biopython.org) | ~47 lines, without blank lines and comments |
| EDAM mapping for the service (`mappings/edam-formats.json` of the artifact) | 10 lines |
| Entry-point declaration (`pyproject.toml`) | 2 lines |
| Derived service image with the plugin (`Dockerfile`) | 5 instructions |
| Changes to format-validator, the service or the CWL runner | 0 lines |

The plugin needs format-validator ≥ 0.4.0 (`registry.load_plugins()`, METADATA and CONTENT modes) and runs in the service image with the EO plug-in, `ghcr.io/dfg-sos/file-format-service-eo:0.4.0` (format-validator 0.5.0, whose core defines no formats). In the evaluation, the Bio scenarios with runtime checks (Bio F2, F3, F5 and OK.1 in `scenarios/scenarios.yml`) run the unchanged runner v0.2.0 on EDAM-annotated workflows against this image, and so do the FASTQ copy chains of the overhead runs (RQ2(b) and (c), `bench/`):

```sh
docker build -t file-format-service-eo-bio:0.4.0 plugins/format-validator-bio
docker run -d --name sos-ffs -p 8000:8000 -v "$PWD/mappings:/app/mappings:ro" \
  file-format-service-eo-bio:0.4.0
```

The service reads every mapping file in `/app/mappings`: the artifact's `mappings/` holds the EO and the EDAM mapping. `tests/data/edam-formats.json` links to the latter, for the tests; the plugin itself ships only validators.

## Usage

```python
from pathlib import Path
from format_validator import FileInput, FormatIdentifier, ValidationMode, build_request, validate
from format_validator.registry import registry

registry.load_plugins()
validate(build_request(FormatIdentifier("FASTQ"), FileInput(path=Path("reads.fastq")), ValidationMode.CONTENT))
```

CONTENT mode parses the whole plain-text (uncompressed) file with Biopython's `SeqIO` (`fasta`, `fastq`, i.e. Sanger/Phred+33) and fails on the first error Biopython reports; the plugin adds no rules of its own. METADATA mode parses only the first record, because neither format has a header: this catches a file of the other format, or of no sequence format, at a cost independent of the file size. For FASTQ, Biopython's parser is the reference implementation of the format's definition ([Cock et al. 2010](https://doi.org/10.1093/nar/gkp1137)): it checks the four-line records, matching captions, equal sequence and quality lengths, and the quality characters. Because FASTQ has no header or index, CONTENT mode reads every record, so its cost grows linearly with the file size. The abstract EDAM *Sequence record format* (`format_1919`) is declared as `SequenceRecord` with FASTA and FASTQ as leaves; format-validator validates it like the EO plug-in's abstract formats (`GISRaster`, `GISVector`): a file is valid if it is valid as a leaf whose extension matches; validation stops at the first such leaf the file is valid as. FASTA has little structure: Biopython accepts a record without a sequence, and a FASTA file cut off inside a sequence is still valid FASTA.

```sh
uv sync && uv run pytest
```
