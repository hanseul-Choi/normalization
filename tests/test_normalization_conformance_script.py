"""Unit tests for the normalization conformance checker
(`scripts/check_normalization_conformance.py`).

These tests exercise the checker's *logic* (parsing + UAX #15 invariant
checks) against small embedded fixtures, so they run offline without
downloading the full NormalizationTest.txt from unicode.org. The full-suite
run and its results live in docs/unicode-normalization-conformance-report.md.
"""
from __future__ import annotations

import unicodedata

from scripts.check_normalization_conformance import (
    Report,
    check_line,
    parse_cps,
    parse_test_lines,
    run_part1_fill_check,
    run_suite,
)

# A handful of real lines lifted from NormalizationTest.txt (Part0 and Part1),
# covering combining-mark reordering, canonical composition/decomposition,
# and compatibility (NFKC/NFKD) folding of a fullwidth character.
SAMPLE_TEST_TXT = """\
# NormalizationTest-sample.txt
@Part0 # Specific cases
1E0A;1E0A;0044 0307;1E0A;0044 0307; # (Ḋ; Ḋ; D+dot above; Ḋ; D+dot above; )
0045 0300;00C8;0045 0300;00C8;0045 0300; # (E+grave; È; E+grave; È; E+grave; )
@Part1 # Character by character test
00C5;00C5;0041 030A;00C5;0041 030A; # (Å; Å; A+ring above; Å; A+ring above; ) LATIN CAPITAL LETTER A WITH RING ABOVE
FF21;FF21;FF21;0041;0041; # (Ａ; Ａ; Ａ; A; A; ) FULLWIDTH LATIN CAPITAL LETTER A
"""


def test_parse_cps_decodes_hex_code_points():
    assert parse_cps("0041") == "A"
    assert parse_cps("0044 0307") == "Ḋ"


def test_parse_test_lines_extracts_parts_and_columns(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text(SAMPLE_TEST_TXT, encoding="utf-8")

    rows = list(parse_test_lines(str(path)))
    assert len(rows) == 4
    parts = [r[0] for r in rows]
    assert parts == ["Part0", "Part0", "Part1", "Part1"]

    # Last row: FF21;FF21;FF21;0041;0041;
    _part, _lineno, _raw_line, c1, _c2, _c3, c4, c5 = rows[-1]
    assert c1 == "Ａ"
    assert c4 == "A"
    assert c5 == "A"


def test_check_line_passes_for_conformant_real_unicode_data():
    """Using the real stdlib unicodedata, correct NormalizationTest.txt rows
    must produce zero failures."""
    report = Report(impl_name="stdlib", unicode_version=unicodedata.unidata_version)
    rows = [
        # Å composed/decomposed pair
        ("Part1", 1, "sample", "Å", "Å", "Å", "Å", "Å"),
        # Fullwidth A -> NFKC/NFKD fold to ASCII A
        ("Part1", 2, "sample", "Ａ", "Ａ", "Ａ", "A", "A"),
    ]
    for part, lineno, raw_line, c1, c2, c3, c4, c5 in rows:
        check_line(unicodedata, part, lineno, raw_line, c1, c2, c3, c4, c5, report)

    assert report.total_checks == 2 * 20
    assert report.failures == []


def test_check_line_detects_a_broken_normalize_implementation():
    """A stand-in implementation with a deliberately wrong NFC must be
    caught by the checker (i.e. it doesn't just rubber-stamp everything)."""

    class BrokenImpl:
        def normalize(self, form: str, s: str) -> str:
            if form == "NFC":
                return s  # pretend NFC is a no-op, which is wrong for decomposed input
            return unicodedata.normalize(form, s)

        def category(self, ch: str) -> str:
            return unicodedata.category(ch)

    report = Report(impl_name="broken", unicode_version="test")
    check_line(
        BrokenImpl(), "Part1", 1, "sample",
        c1="Å", c2="Å", c3="Å", c4="Å", c5="Å",
        report=report,
    )
    assert len(report.failures) > 0
    assert any("NFC" in f.rule for f in report.failures)


def test_run_suite_on_sample_file_is_conformant(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text(SAMPLE_TEST_TXT, encoding="utf-8")

    report = run_suite(str(path), unicodedata, "stdlib", unicodedata.unidata_version)
    assert report.total_lines == 4
    assert report.failures == []
    assert report.part1_tested_chars == {"Å", "Ａ"}


def test_run_part1_fill_check_flags_a_non_inert_untested_character(tmp_path):
    """Sanity-check the 'every other assigned character is normalization-inert'
    rule: feed it a report where a compatibility character (e.g. fullwidth A)
    was NOT explicitly tested, and confirm the fill check flags it instead of
    silently passing."""
    report = Report(impl_name="stdlib", unicode_version=unicodedata.unidata_version)
    report.part1_tested_chars = set()  # nothing explicitly tested

    # Limit the scan to a tiny range containing FF21 (FULLWIDTH LATIN CAPITAL A),
    # which is NOT normalization-inert under NFKC/NFKD -- full 0x10FFFF sweep
    # is covered in the real report, not in this fast unit test.
    class RangeLimitedProxy:
        def normalize(self, form, s):
            return unicodedata.normalize(form, s)

        def category(self, ch):
            return unicodedata.category(ch)

    run_part1_fill_check(RangeLimitedProxy(), report, max_cp=0xFF21)
    assert report.part1_fill_checked > 0
    assert any("FF21" in msg for msg in report.part1_fill_failures)
