"""End-to-end tests: the installed plugin is discovered through its entry point and validates files."""
import json
from pathlib import Path

import pytest
from format_validator import (
    FileInput,
    FormatIdentifier,
    FormatTranslator,
    ValidationMode,
    ValidationStatus,
    build_request,
    supported_formats,
    validate,
)
from format_validator.registry import registry

DATA = Path(__file__).parent / "data"
MAPPING = DATA / "edam-formats.json"
EDAM = "http://edamontology.org/"


@pytest.fixture(scope="module", autouse=True)
def plugins():
    assert "bio" in registry.load_plugins()


def run(identifier: FormatIdentifier, name: str, mode=ValidationMode.FULL):
    return validate(build_request(identifier, FileInput(path=DATA / name), mode))


def test_formats_supported():
    assert {FormatIdentifier("FASTA"), FormatIdentifier("FASTQ"), FormatIdentifier("SequenceRecord")} <= set(
        supported_formats()
    )


def test_edam_mapping():
    # the service keys its translator by ontology_uri + local identifier
    mapping = json.loads(MAPPING.read_text())
    translator = FormatTranslator({mapping["ontology_uri"] + k: v for k, v in mapping["mappings"].items()})
    assert translator.to_local(EDAM + "format_1929") == FormatIdentifier("FASTA")
    assert translator.to_local(EDAM + "format_1930") == FormatIdentifier("FASTQ")
    assert translator.to_local(EDAM + "format_1919") == FormatIdentifier("SequenceRecord")


@pytest.mark.parametrize(
    "fmt, name, status",
    [
        ("FASTA", "valid.fasta", ValidationStatus.SUCCESS),
        ("FASTA", "invalid.fasta", ValidationStatus.FAILURE),
        ("FASTQ", "valid.fastq", ValidationStatus.SUCCESS),
        ("FASTQ", "invalid.fastq", ValidationStatus.FAILURE),
        ("FASTA", "valid.fastq", ValidationStatus.FAILURE),  # extension mismatch
        ("SequenceRecord", "valid.fasta", ValidationStatus.SUCCESS),  # abstract: valid as a leaf
        ("SequenceRecord", "valid.fastq", ValidationStatus.SUCCESS),
        ("SequenceRecord", "invalid.fastq", ValidationStatus.FAILURE),
        ("SequenceRecord", "edam-formats.json", ValidationStatus.FAILURE),  # no leaf has this extension
    ],
)
def test_validate(fmt, name, status):
    assert run(FormatIdentifier(fmt), name).status == status


@pytest.mark.parametrize(
    "content, message",
    [
        ("ACGT\n>a\nACGT\n", "comments at the beginning"),  # sequence before the first header
        ("@r\nACGT\n+\nIIII\n", "comments at the beginning"),  # FASTQ content
    ],
)
def test_fasta_problems(tmp_path, content, message):
    path = tmp_path / "x.fasta"
    path.write_text(content)
    result = validate(build_request(FormatIdentifier("FASTA"), FileInput(path=path), ValidationMode.FULL))
    assert result.status == ValidationStatus.FAILURE
    assert message in str(result.to_dict())


@pytest.mark.parametrize(
    "content, message",
    [
        ("@r\nACGT\n+\n", "end of file"),  # truncated record
        ("r\nACGT\n+\nIIII\n", "should start with '@'"),
        ("@r\nACGT\n+s\nIIII\n", "captions differ"),
        ("@r\nACGT\n+\nIII\n", "Lengths of sequence and quality values differs"),
        ("@r\nACGT\n+\nII I\n", "Invalid character"),
        (">r\nACGT\n", "should start with '@'"),  # FASTA content
    ],
)
def test_fastq_problems(tmp_path, content, message):
    path = tmp_path / "x.fastq"
    path.write_text(content)
    result = validate(build_request(FormatIdentifier("FASTQ"), FileInput(path=path), ValidationMode.FULL))
    assert result.status == ValidationStatus.FAILURE
    assert message in str(result.to_dict())


def test_binary_file_fails(tmp_path):
    path = tmp_path / "x.fastq"
    path.write_bytes(b"\x89PNG\r\n\x1a\n\xff")
    result = validate(build_request(FormatIdentifier("FASTQ"), FileInput(path=path), ValidationMode.FULL))
    assert result.status == ValidationStatus.FAILURE


def test_basic_mode_does_not_read(tmp_path):
    assert run(FormatIdentifier("FASTA"), "missing.fasta", ValidationMode.BASIC).status == ValidationStatus.SUCCESS
