"""Validate secnorm's Unicode normalization backend against Unicode's official
NormalizationTest.txt conformance suite (UAX #15).

secnorm.steps.unicode_step normalizes text via unicodedata2 (falling back to
the stdlib unicodedata if unicodedata2 isn't installed) -- see
docs/03-step1-unicode-normalization.md. This script exercises exactly those
two normalize() implementations against the UAX #15 conformance rules.

Usage:
    python scripts/check_normalization_conformance.py path/to/NormalizationTest.txt

Download the test file from:
    https://www.unicode.org/Public/UCD/latest/ucd/NormalizationTest.txt

Related: docs/unicode-normalization-conformance-report.md (latest results),
tests/test_normalization_conformance_script.py (unit tests for this script).
"""
from __future__ import annotations

import sys
import unicodedata as stdlib_unicodedata
from dataclasses import dataclass, field
from typing import Protocol

try:
    import unicodedata2 as ud2
    HAVE_UD2 = True
except ImportError:
    ud2 = None
    HAVE_UD2 = False


class NormalizeImpl(Protocol):
    def normalize(self, form: str, s: str) -> str: ...
    def category(self, ch: str) -> str: ...


def parse_cps(field_str: str) -> str:
    return "".join(chr(int(cp, 16)) for cp in field_str.split())


@dataclass
class Failure:
    part: str
    lineno: int
    rule: str
    raw_line: str
    detail: str


@dataclass
class Report:
    impl_name: str
    unicode_version: str
    total_lines: int = 0
    total_checks: int = 0
    failures: list[Failure] = field(default_factory=list)
    part1_tested_chars: set[str] = field(default_factory=set)
    part1_fill_checked: int = 0
    part1_fill_failures: list[str] = field(default_factory=list)


def check_line(
    impl: NormalizeImpl,
    part: str,
    lineno: int,
    raw_line: str,
    c1: str,
    c2: str,
    c3: str,
    c4: str,
    c5: str,
    report: Report,
) -> None:
    """Apply the UAX #15 conformance invariants for one test line."""

    def nfc(s: str) -> str:
        return impl.normalize("NFC", s)

    def nfd(s: str) -> str:
        return impl.normalize("NFD", s)

    def nfkc(s: str) -> str:
        return impl.normalize("NFKC", s)

    def nfkd(s: str) -> str:
        return impl.normalize("NFKD", s)

    checks = [
        ("NFC: c2==NFC(c1)", c2, nfc(c1)),
        ("NFC: c2==NFC(c2)", c2, nfc(c2)),
        ("NFC: c2==NFC(c3)", c2, nfc(c3)),
        ("NFC: c4==NFC(c4)", c4, nfc(c4)),
        ("NFC: c4==NFC(c5)", c4, nfc(c5)),
        ("NFD: c3==NFD(c1)", c3, nfd(c1)),
        ("NFD: c3==NFD(c2)", c3, nfd(c2)),
        ("NFD: c3==NFD(c3)", c3, nfd(c3)),
        ("NFD: c5==NFD(c4)", c5, nfd(c4)),
        ("NFD: c5==NFD(c5)", c5, nfd(c5)),
        ("NFKC: c4==NFKC(c1)", c4, nfkc(c1)),
        ("NFKC: c4==NFKC(c2)", c4, nfkc(c2)),
        ("NFKC: c4==NFKC(c3)", c4, nfkc(c3)),
        ("NFKC: c4==NFKC(c4)", c4, nfkc(c4)),
        ("NFKC: c4==NFKC(c5)", c4, nfkc(c5)),
        ("NFKD: c5==NFKD(c1)", c5, nfkd(c1)),
        ("NFKD: c5==NFKD(c2)", c5, nfkd(c2)),
        ("NFKD: c5==NFKD(c3)", c5, nfkd(c3)),
        ("NFKD: c5==NFKD(c4)", c5, nfkd(c4)),
        ("NFKD: c5==NFKD(c5)", c5, nfkd(c5)),
    ]
    for rule, expected, actual in checks:
        report.total_checks += 1
        if expected != actual:
            report.failures.append(
                Failure(
                    part=part,
                    lineno=lineno,
                    rule=rule,
                    raw_line=raw_line,
                    detail=(
                        f"expected={' '.join(f'U+{ord(c):04X}' for c in expected)!r} "
                        f"actual={' '.join(f'U+{ord(c):04X}' for c in actual)!r}"
                    ),
                )
            )


def parse_test_lines(path: str):
    """Yield (part, lineno, raw_line, c1..c5) tuples from a NormalizationTest.txt file."""
    current_part = "?"
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.rstrip("\n")
            if line.startswith("@Part"):
                current_part = line.split("#")[0].strip().lstrip("@")
                continue
            if not line or line.startswith("#"):
                continue
            data = line.split("#")[0].strip()
            if not data:
                continue
            cols = [c.strip() for c in data.split(";") if c.strip() != ""]
            if len(cols) < 5:
                continue
            c1, c2, c3, c4, c5 = (parse_cps(c) for c in cols[:5])
            yield current_part, lineno, line, c1, c2, c3, c4, c5


def run_suite(path: str, impl: NormalizeImpl, impl_name: str, unicode_version: str) -> Report:
    report = Report(impl_name=impl_name, unicode_version=unicode_version)
    for part, lineno, raw_line, c1, c2, c3, c4, c5 in parse_test_lines(path):
        report.total_lines += 1
        check_line(impl, part, lineno, raw_line, c1, c2, c3, c4, c5, report)
        if part == "Part1":
            report.part1_tested_chars.add(c1)
    return report


def run_part1_fill_check(impl: NormalizeImpl, report: Report, max_cp: int = 0x10FFFF) -> None:
    """Rule 2: every code point assigned in `impl`'s own Unicode version that is
    NOT explicitly listed in Part 1 must be its own NFC/NFD/NFKC/NFKD
    (i.e. normalization-inert)."""
    tested = report.part1_tested_chars
    for cp in range(max_cp + 1):
        if 0xD800 <= cp <= 0xDFFF:  # surrogates, not valid scalar values
            continue
        ch = chr(cp)
        if ch in tested:
            continue
        if impl.category(ch) == "Cn":
            continue
        report.part1_fill_checked += 1
        for form in ("NFC", "NFD", "NFKC", "NFKD"):
            out = impl.normalize(form, ch)
            if out != ch:
                report.part1_fill_failures.append(
                    f"U+{cp:04X} ({impl.category(ch)}): {form}(X) = "
                    f"{' '.join(f'U+{ord(c):04X}' for c in out)} != X"
                )


def summarize(report: Report, max_shown: int = 20) -> str:
    lines = [f"### {report.impl_name} (Unicode {report.unicode_version})", ""]
    lines.append(f"- Explicit test lines processed: {report.total_lines}")
    lines.append(f"- Individual conformance checks run: {report.total_checks}")
    lines.append(f"- Failures (Part 0-3 explicit lines): {len(report.failures)}")
    lines.append(
        f"- Part 1 'fill' code points checked (assigned, not explicitly listed): "
        f"{report.part1_fill_checked}"
    )
    lines.append(f"- Part 1 'fill' failures: {len(report.part1_fill_failures)}")
    lines.append("")
    if report.failures:
        by_rule: dict[str, list[Failure]] = {}
        for f in report.failures:
            by_rule.setdefault(f.rule, []).append(f)
        lines.append("Failure breakdown by rule:")
        for rule, fails in sorted(by_rule.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"- `{rule}`: {len(fails)}")
        lines.append("")
        lines.append(f"First {max_shown} failing lines:")
        for f in report.failures[:max_shown]:
            lines.append(f"- [{f.part} L{f.lineno}] `{f.rule}` — {f.raw_line.split('#')[0].strip()} — {f.detail}")
        lines.append("")
    if report.part1_fill_failures:
        lines.append(f"First {max_shown} Part-1-fill failures:")
        for msg in report.part1_fill_failures[:max_shown]:
            lines.append(f"- {msg}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    path = sys.argv[1]

    with open(path, encoding="utf-8") as f:
        header = f.readline()
    file_version = header.strip().split("-")[-1].replace(".txt", "")

    results = []
    if HAVE_UD2:
        r = run_suite(path, ud2, "unicodedata2 (secnorm.steps.unicode_step primary backend)", ud2.unidata_version)
        run_part1_fill_check(ud2, r)
        results.append(r)

    r2 = run_suite(
        path,
        stdlib_unicodedata,
        "stdlib unicodedata (secnorm.steps.unicode_step fallback backend)",
        stdlib_unicodedata.unidata_version,
    )
    run_part1_fill_check(stdlib_unicodedata, r2)
    results.append(r2)

    print(f"# Test file: NormalizationTest-{file_version}.txt (source: unicode.org)\n")
    for r in results:
        print(summarize(r))
        print()


if __name__ == "__main__":
    main()
