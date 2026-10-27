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
    assert {FormatIdentifier("FASTA"), FormatIdentifier("FASTQ")} <= set(supported_formats())


def test_edam_mapping():
    # the service keys its translator by ontology_uri + local identifier
    mapping = json.loads(MAPPING.read_text())
    translator = FormatTranslator({mapping["ontology_uri"] + k: v for k, v in mapping["mappings"].items()})
    assert translator.to_local(EDAM + "format_1929") == FormatIdentifier("FASTA")
    assert translator.to_local(EDAM + "format_1930") == FormatIdentifier("FASTQ")


@pytest.mark.parametrize(
    "fmt, name, status",
    [
        ("FASTA", "valid.fasta", ValidationStatus.SUCCESS),
        ("FASTA", "invalid.fasta", ValidationStatus.FAILURE),
        ("FASTQ", "valid.fastq", ValidationStatus.SUCCESS),
        ("FASTQ", "invalid.fastq", ValidationStatus.FAILURE),
        ("FASTA", "valid.fastq", ValidationStatus.FAILURE),  # extension mismatch
    ],
)
def test_validate(fmt, name, status):
    assert run(FormatIdentifier(fmt), name).status == status


@pytest.mark.parametrize(
    "content, message",
    [
        ("", "no records"),
        ("ACGT\n", "header starting with '>'"),
        (">\nACGT\n", "no identifier"),
        (">a\n>b\nACGT\n", "no sequence"),
        (">a\nACGT\n>b\n", "no sequence"),
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
        ("", "no records"),
        ("@r\nACGT\n+\n", "truncated"),
        ("r\nACGT\n+\nIIII\n", "header starting with '@'"),
        ("@r\nACGT\n-\nIIII\n", "separator"),
        ("@r\nACGT\n+s\nIIII\n", "differs from the header"),
        ("@r\nAC GT\n+\nIIIII\n", "Invalid sequence"),
        ("@r\nACGT\n+\nII\x7fI\n", "Invalid quality"),
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
    assert "not ASCII" in str(result.to_dict())


def test_basic_mode_does_not_read(tmp_path):
    assert run(FormatIdentifier("FASTA"), "missing.fasta", ValidationMode.BASIC).status == ValidationStatus.SUCCESS
