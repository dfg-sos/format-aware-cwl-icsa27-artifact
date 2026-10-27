"""FASTA (EDAM format_1929) and FASTQ (EDAM format_1930) validators.

FASTA: https://www.ncbi.nlm.nih.gov/genbank/fastaformat/
FASTQ: Cock et al. (2010), https://doi.org/10.1093/nar/gkp1137
"""
from abc import abstractmethod
from typing import Iterator, List, Optional, Tuple

from format_validator.model import (
    Cause,
    Error,
    FileFormatValidator,
    FormatIdentifier,
    ValidationRequest,
    ValidationResult,
)
from format_validator.registry import registry

from . import FASTA_ID, FASTQ_ID

# IUPAC nucleotide and amino acid codes are letters; '*' ends a protein, '-' is a gap.
FASTA_SEQUENCE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz*-")
FASTQ_SEQUENCE_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-")
# Phred qualities are encoded as printable ASCII from '!' (33) to '~' (126).
FASTQ_QUALITY_CHARS = frozenset(chr(c) for c in range(33, 127))

Problem = Tuple[int, str]


class SequenceFileValidator(FileFormatValidator):
    """Reads a plain-text sequence file line by line and reports the first malformed line."""

    def assert_can_open(self, request: ValidationRequest) -> ValidationResult:
        path = request.actual_file.path
        try:
            with open(path, encoding="ascii") as f:
                problem = self.find_problem(enumerate((line.rstrip("\r\n") for line in f), start=1))
        except UnicodeDecodeError as e:
            return ValidationResult.failure(
                request, Error(message=f"File is not ASCII text: {e}", cause=Cause.STRUCTURAL_MALFORMED)
            )
        except OSError as e:
            return ValidationResult.failure(
                request, Error(message=f"Cannot read file: {e}", cause=Cause.FILE_OPEN_ERROR)
            )
        if problem is not None:
            line_no, message = problem
            return ValidationResult.failure(
                request,
                Error(message=f"Line {line_no}: {message}", cause=Cause.STRUCTURAL_MALFORMED),
            )
        return ValidationResult.success(request)

    @abstractmethod
    def find_problem(self, lines: Iterator[Tuple[int, str]]) -> Optional[Problem]:
        """Returns the line number and description of the first problem, or ``None``."""


@registry.register(FormatIdentifier(FASTA_ID))
class FASTAValidator(SequenceFileValidator):

    def get_extensions(self) -> List[str]:
        return [".fasta", ".fa", ".fna", ".ffn", ".faa", ".frn", ".fas"]

    def find_problem(self, lines: Iterator[Tuple[int, str]]) -> Optional[Problem]:
        records = 0
        header_line = None  # line of the current header while its sequence is still empty
        for line_no, line in lines:
            if not line.strip():
                continue
            if line.startswith(">"):
                if header_line is not None:
                    return header_line, "Record has no sequence."
                if not line[1:].strip():
                    return line_no, "Header has no identifier."
                records += 1
                header_line = line_no
                continue
            if records == 0:
                return line_no, "Expected a header starting with '>'."
            bad = set(line.strip()) - FASTA_SEQUENCE_CHARS
            if bad:
                return line_no, f"Invalid sequence characters: {''.join(sorted(bad))!r}."
            header_line = None
        if header_line is not None:
            return header_line, "Record has no sequence."
        if records == 0:
            return 1, "File contains no records."
        return None


@registry.register(FormatIdentifier(FASTQ_ID))
class FASTQValidator(SequenceFileValidator):
    """Four-line FASTQ records: ``@id``, sequence, ``+[id]`` and qualities of the same length."""

    def get_extensions(self) -> List[str]:
        return [".fastq", ".fq"]

    def find_problem(self, lines: Iterator[Tuple[int, str]]) -> Optional[Problem]:
        records = 0
        record: List[Tuple[int, str]] = []
        last_line_no = 0
        for line_no, line in lines:
            last_line_no = line_no
            if not record and not line.strip():
                continue  # blank lines between records and at the end
            record.append((line_no, line))
            if len(record) == 4:
                problem = self._check_record(record)
                if problem is not None:
                    return problem
                records += 1
                record = []
        if record:
            return last_line_no, f"Record starting at line {record[0][0]} is truncated."
        if records == 0:
            return 1, "File contains no records."
        return None

    def _check_record(self, record: List[Tuple[int, str]]) -> Optional[Problem]:
        (header_no, header), (seq_no, seq), (plus_no, plus), (qual_no, qual) = record
        if not header.startswith("@") or not header[1:].strip():
            return header_no, "Expected a header starting with '@' followed by an identifier."
        bad = set(seq) - FASTQ_SEQUENCE_CHARS
        if bad:
            return seq_no, f"Invalid sequence characters: {''.join(sorted(bad))!r}."
        if not plus.startswith("+"):
            return plus_no, "Expected a separator line starting with '+'."
        if plus[1:] and plus[1:] != header[1:]:
            return plus_no, "Separator repeats an identifier that differs from the header."
        if len(qual) != len(seq):
            return qual_no, f"Quality length {len(qual)} differs from sequence length {len(seq)}."
        bad = set(qual) - FASTQ_QUALITY_CHARS
        if bad:
            return qual_no, f"Invalid quality characters: {''.join(sorted(bad))!r}."
        return None
