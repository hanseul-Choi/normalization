"""Unit tests for secnorm CLI (`src/secnorm/cli.py`)."""

import io
import json
import pytest
from secnorm.cli import main
from secnorm.pipeline import PIPELINE_VERSION


def test_cli_simple_text(capsys):
    ret = main(["Hello   world!"])
    assert ret == 0
    out, err = capsys.readouterr()
    assert out.strip() == "Hello world!"


def test_cli_preset_option(capsys):
    ret = main(["аpple.com", "--preset", "security_strict"])
    assert ret == 0
    out, err = capsys.readouterr()
    assert out.strip() == "apple.com"


def test_cli_json_output(capsys):
    ret = main(["аpple.com", "--json"])
    assert ret == 0
    out, err = capsys.readouterr()
    data = json.loads(out)
    assert data["raw_text"] == "аpple.com"
    assert data["normalized_text"] == "apple.com"
    assert any(f["category"] == "homoglyph" for f in data["flags"])


def test_cli_json_no_raw(capsys):
    ret = main(["аpple.com", "--json", "--no-raw"])
    assert ret == 0
    out, err = capsys.readouterr()
    data = json.loads(out)
    assert data["raw_text"] is None
    assert data["normalized_text"] == "apple.com"


def test_cli_stdin_input(capsys, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("Testing   stdin   pipe."))
    ret = main([])
    assert ret == 0
    out, err = capsys.readouterr()
    assert out.strip() == "Testing stdin pipe."


def test_cli_no_input_tty(capsys, monkeypatch):
    fake_stdin = io.StringIO("")
    monkeypatch.setattr(fake_stdin, "isatty", lambda: True)
    monkeypatch.setattr("sys.stdin", fake_stdin)

    ret = main([])
    assert ret == 1
    out, err = capsys.readouterr()
    assert "usage: secnorm" in err.lower()


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    out, err = capsys.readouterr()
    assert f"secnorm {PIPELINE_VERSION}" in out


def test_cli_input_and_output_file(tmp_path):
    in_file = tmp_path / "in.txt"
    out_file = tmp_path / "out.txt"
    in_file.write_text("Hello   world!\nаpple.com\n", encoding="utf-8")

    ret = main(["-i", str(in_file), "-o", str(out_file)])
    assert ret == 0
    assert out_file.read_text(encoding="utf-8").splitlines() == [
        "Hello world!",
        "apple.com",
    ]


def test_cli_file_jsonl_format(tmp_path):
    in_file = tmp_path / "in.txt"
    out_file = tmp_path / "out.jsonl"
    in_file.write_text("аpple.com\n", encoding="utf-8")

    ret = main(["-i", str(in_file), "-o", str(out_file), "--format", "jsonl"])
    assert ret == 0

    lines = out_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["normalized_text"] == "apple.com"
    assert data["raw_text"] == "аpple.com"


def test_cli_input_file_to_stdout(tmp_path, capsys):
    in_file = tmp_path / "in.txt"
    in_file.write_text("Line   one\nLine   two\n", encoding="utf-8")

    ret = main(["-i", str(in_file)])
    assert ret == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == ["Line one", "Line two"]


def test_cli_single_text_to_output_file(tmp_path):
    out_file = tmp_path / "out.txt"
    ret = main(["Test   sentence", "-o", str(out_file)])
    assert ret == 0
    assert out_file.read_text(encoding="utf-8").strip() == "Test sentence"
