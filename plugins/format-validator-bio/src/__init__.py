"""Bioinformatics sequence formats for format-validator.

The validators register themselves when ``format_validator.registry.registry.load_plugins()``
imports ``format_validator_bio.validators`` through the ``format_validator.validators`` entry point.
"""

FASTA_ID = "FASTA"
FASTQ_ID = "FASTQ"
