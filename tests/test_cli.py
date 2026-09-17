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
