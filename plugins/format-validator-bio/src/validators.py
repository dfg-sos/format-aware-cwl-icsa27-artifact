"""FASTA (EDAM format_1929) and FASTQ (EDAM format_1930) validators.

METADATA mode parses the first record with Biopython's ``SeqIO``, as the formats have no header; CONTENT mode parses
the whole file: a file is valid if Biopython reads every record without an error. The plugin adds no rules of its own. For FASTQ (``fastq``, i.e. Sanger, Phred+33), Biopython's parser is
the reference implementation of the format's definition: Cock et al. (2010), https://doi.org/10.1093/nar/gkp1137.
"""
from typing import List

from Bio import SeqIO
from format_validator.model import (
    Cause,
    Error,
    FileFormatValidator,
    FormatIdentifier,
    ValidationRequest,
    ValidationResult,
)
from format_validator.registry import registry

from . import FASTA_ID, FASTQ_ID, SEQUENCE_ID


class SequenceFileValidator(FileFormatValidator):
    """Parses a plain-text sequence file with Biopython and fails on the first error it reports."""

    seqio_format: str  # Biopython's name of the format

    def assert_can_open(self, request: ValidationRequest) -> ValidationResult:
        return self._parse(request, first_record_only=True)

    def assert_content(self, request: ValidationRequest) -> ValidationResult:
        return self._parse(request, first_record_only=False)

    def _parse(self, request: ValidationRequest, first_record_only: bool) -> ValidationResult:
        path = request.actual_file.path
        try:
            with open(path) as handle:
                for _ in SeqIO.parse(handle, self.seqio_format):
                    if first_record_only:
                        break
        except ValueError as e:  # Biopython's parse errors; also UnicodeDecodeError
            return ValidationResult.failure(
                request,
                Error(
                    message=f"Biopython cannot parse the file as {self.seqio_format}: {e}",
                    cause=Cause.STRUCTURAL_MALFORMED,
                ),
            )
        except OSError as e:
            return ValidationResult.failure(
                request, Error(message=f"Cannot read file: {e}", cause=Cause.FILE_OPEN_ERROR)
            )
        return ValidationResult.success(request)


@registry.register(FormatIdentifier(FASTA_ID))
class FASTAValidator(SequenceFileValidator):
    seqio_format = "fasta"

    def get_extensions(self) -> List[str]:
        return [".fasta", ".fa", ".fna", ".ffn", ".faa", ".frn", ".fas"]


@registry.register(FormatIdentifier(FASTQ_ID))
class FASTQValidator(SequenceFileValidator):
    seqio_format = "fastq"

    def get_extensions(self) -> List[str]:
        return [".fastq", ".fq"]


# The abstract EDAM "Sequence record format" (format_1919): format-validator validates it against its leaves, as the
# built-in abstract EO formats (GISRaster, GISVector): valid if valid as a leaf whose extension matches.
FormatIdentifier(SEQUENCE_ID, children_ids=[FASTA_ID, FASTQ_ID], is_abstract=True)
