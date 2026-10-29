# format-validator-bio

Demo plugin for [format-validator](https://github.com/dfg-sos/file-format-validator) that adds FASTA ([EDAM format_1929](http://edamontology.org/format_1929)) and FASTQ ([EDAM format_1930](http://edamontology.org/format_1930)) validators without changing the core. It is discovered through the `format_validator.validators` entry point declared in [pyproject.toml](pyproject.toml).

## Why it is in this artifact

The paper claims that the architecture extends to other domains and is ontology-neutral (R2, design decision D2: validators as discovered plug-ins). This package is the evidence: a second domain (bioinformatics, EDAM ontology) added as an ordinary Python package, with **no changes** to the validator core or the service. What it took:

| Part | Size |
|---|---|
| Validators (`src/validators.py`, `src/__init__.py`), on [Biopython](https://biopython.org) | ~47 lines, without blank lines and comments |
| EDAM mapping for the service (`mappings/edam-formats.json` of the artifact) | 10 lines |
| Entry-point declaration (`pyproject.toml`) | 2 lines |
| Derived service image with the plugin (`Dockerfile`) | 5 instructions |
| Changes to format-validator, the service or the CWL runner | 0 lines |

The plugin needs format-validator ≥ 0.3.0 (`registry.load_plugins()`) and runs in the service image `ghcr.io/dfg-sos/file-format-service:0.2.0`. In the evaluation, the Bio scenarios with runtime checks (Bio F2, F3, F5 and OK.1 in `scenarios/scenarios.yml`) run the unchanged runner v0.1.0 on EDAM-annotated workflows against this image:

```sh
docker build -t file-format-service-eo-bio:0.2.0 plugins/format-validator-bio
docker run -d --name sos-ffs -p 8000:8000 -v "$PWD/mappings:/app/mappings:ro" \
  file-format-service-eo-bio:0.2.0
```

The service reads every mapping file in `/app/mappings`: the artifact's `mappings/` holds the EO and the EDAM mapping. `tests/data/edam-formats.json` links to the latter, for the tests; the plugin itself ships only validators.

## Usage

```python
from pathlib import Path
from format_validator import FileInput, FormatIdentifier, ValidationMode, build_request, validate
from format_validator.registry import registry

registry.load_plugins()
validate(build_request(FormatIdentifier("FASTQ"), FileInput(path=Path("reads.fastq")), ValidationMode.FULL))
```

FULL mode parses the whole plain-text (uncompressed) file with Biopython's `SeqIO` (`fasta`, `fastq`, i.e. Sanger/Phred+33) and fails on the first error Biopython reports; the plugin adds no rules of its own. For FASTQ, Biopython's parser is the reference implementation of the format's definition ([Cock et al. 2010](https://doi.org/10.1093/nar/gkp1137)): it checks the four-line records, matching captions, equal sequence and quality lengths, and the quality characters. Because FASTQ has no header or index, this reads every record, so its cost grows linearly with the file size, unlike the EO validators, which open a file with GDAL and read its header. The abstract EDAM *Sequence record format* (`format_1919`) is declared as `SequenceRecord` with FASTA and FASTQ as leaves; format-validator validates it like its abstract EO formats (`GISRaster`, `GISVector`): a file is valid if it is valid as a leaf whose extension matches. FASTA has little structure: Biopython accepts a record without a sequence, and a FASTA file cut off inside a sequence is still valid FASTA.

```sh
uv sync && uv run pytest
```
