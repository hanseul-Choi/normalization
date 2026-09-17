"""Unit and integration tests for streaming and file I/O normalization (`src/secnorm/streaming.py`)."""

import json
from pathlib import Path
import pytest
import secnorm


def test_normalize_stream_basic():
    corpus = [
        "Hello   world",
        "аpple.com",
        "Important\u200bhidden",
    ]
    results = list(secnorm.normalize_stream(corpus, preset="security_balanced"))
    assert len(results) == 3
    assert results[0].normalized_text == "Hello world"
    assert results[1].normalized_text == "apple.com"
    assert results[2].normalized_text == "Importanthidden"


def test_normalize_stream_parallel_and_chunks():
    corpus = [f"Item number {i}   with   spaces" for i in range(25)]
    results = list(secnorm.normalize_stream(corpus, preset="minimal", chunk_size=5, n_jobs=2))
    assert len(results) == 25
    for i, res in enumerate(results):
        assert res.normalized_text == f"Item number {i} with spaces"


def test_normalize_stream_invalid_chunk_size():
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        list(secnorm.normalize_stream(["test"], chunk_size=0))


def test_normalize_file_text_format(tmp_path: Path):
    in_file = tmp_path / "input.txt"
    out_file = tmp_path / "output.txt"

    lines = [
        "First line   with spaces",
        "Phishing аpple.com site",
        "Repeated characters coooool!",
    ]
    in_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    processed = secnorm.normalize_file(
        in_file,
        out_file,
        preset="security_balanced",
        format="text",
    )
    assert processed == 3

    out_lines = out_file.read_text(encoding="utf-8").splitlines()
    assert len(out_lines) == 3
    assert out_lines[0] == "First line with spaces"
    assert out_lines[1] == "Phishing apple.com site"
    assert out_lines[2] == "Repeated characters cool!"


def test_normalize_file_jsonl_format(tmp_path: Path):
    in_file = tmp_path / "input.txt"
    out_file = tmp_path / "output.jsonl"

    lines = [
        "Clean text line",
        "Suspicious аpple.com line",
    ]
    in_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    processed = secnorm.normalize_file(
        in_file,
        out_file,
        preset="security_balanced",
        format="jsonl",
        include_raw_text=True,
    )
    assert processed == 2

    raw_json_lines = out_file.read_text(encoding="utf-8").splitlines()
    assert len(raw_json_lines) == 2

    parsed_1 = json.loads(raw_json_lines[0])
    assert parsed_1["raw_text"] == "Clean text line"
    assert parsed_1["normalized_text"] == "Clean text line"

    parsed_2 = json.loads(raw_json_lines[1])
    assert parsed_2["raw_text"] == "Suspicious аpple.com line"
    assert parsed_2["normalized_text"] == "Suspicious apple.com line"
    assert any(f["category"] == "homoglyph" for f in parsed_2["flags"])


def test_normalize_file_jsonl_no_raw_text(tmp_path: Path):
    in_file = tmp_path / "input.txt"
    out_file = tmp_path / "output.jsonl"
    in_file.write_text("Private data here\n", encoding="utf-8")

    secnorm.normalize_file(
        in_file,
        out_file,
        format="jsonl",
        include_raw_text=False,
    )
    parsed = json.loads(out_file.read_text(encoding="utf-8").strip())
    assert parsed["raw_text"] is None
    assert parsed["normalized_text"] == "Private data here"


def test_normalize_file_invalid_format(tmp_path: Path):
    in_file = tmp_path / "in.txt"
    out_file = tmp_path / "out.txt"
    in_file.write_text("hello\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid format"):
        secnorm.normalize_file(in_file, out_file, format="invalid_format")  # type: ignore
