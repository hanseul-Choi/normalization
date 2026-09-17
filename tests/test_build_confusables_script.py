"""Unit tests for build_confusables script (`scripts/build_confusables.py`)."""

from pathlib import Path
import pytest
from scripts.build_confusables import generate_code, main, parse_confusables

SAMPLE_CONFUSABLES_TXT = """# confusables.txt format test
# comment line

0430 ;\t0061 ;\tMA\t# ( \u0430 \u2192 a ) CYRILLIC SMALL LETTER A \u2192 LATIN SMALL LETTER A
03BF ;\t006F ;\tMA\t# ( \u03BF \u2192 o ) GREEK SMALL LETTER OMICRON \u2192 LATIN SMALL LETTER O
0061 ;\t0061 ;\tMA\t# ( a \u2192 a ) ASCII to ASCII should be ignored
"""


def test_parse_confusables_extracts_cross_script():
    mapping = parse_confusables(SAMPLE_CONFUSABLES_TXT)
    assert "\u0430" in mapping
    assert mapping["\u0430"] == "a"
    assert "\u03BF" in mapping
    assert mapping["\u03BF"] == "o"
    # ASCII to ASCII should be excluded
    assert "a" not in mapping


def test_generate_code():
    mapping = {"\u0430": "a", "\u03BF": "o"}
    code = generate_code(mapping, version="16.0.0")
    assert 'CONFUSABLES_VERSION = "16.0.0"' in code
    assert "'\\u0430': 'a'" in code or "'а': 'a'" in code
    assert "CONFUSABLES_MAP: dict[str, str] = {" in code


def test_build_confusables_cli_dry_run(tmp_path: Path, capsys):
    src_file = tmp_path / "test_confusables.txt"
    src_file.write_text(SAMPLE_CONFUSABLES_TXT, encoding="utf-8")

    ret = main(["--source", str(src_file), "--dry-run"])
    assert ret == 0
    out, err = capsys.readouterr()
    assert "Parsed 2 cross-script lookalikes" in out
    assert "Dry-run complete" in out


def test_build_confusables_cli_generate_file(tmp_path: Path):
    src_file = tmp_path / "test_confusables.txt"
    out_file = tmp_path / "generated_confusables.py"
    src_file.write_text(SAMPLE_CONFUSABLES_TXT, encoding="utf-8")

    ret = main(["--source", str(src_file), "--output", str(out_file), "--version", "16.0.0"])
    assert ret == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert 'CONFUSABLES_VERSION = "16.0.0"' in content
    assert "CONFUSABLES_MAP" in content
