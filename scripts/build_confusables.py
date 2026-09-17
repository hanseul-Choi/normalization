#!/usr/bin/env python3
"""Build/update UTS #39 confusables mapping table (`docs/08-step6-obfuscation-normalization.md`).

Parses Unicode Technical Standard #39 `confusables.txt` and generates
`src/secnorm/data/confusables.py`.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

DEFAULT_CONFUSABLES_URL = "https://www.unicode.org/Public/security/16.0.0/confusables.txt"
DEFAULT_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "src" / "secnorm" / "data" / "confusables.py"


def parse_confusables(text: str) -> dict[str, str]:
    """Parse confusables.txt format into source -> target mapping.

    Format:
    <code> ;\t<target_codes> ;\t<type>\t# ( <src> → <target> ) <comment>
    """
    mapping: dict[str, str] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split(";")
        if len(parts) < 2:
            continue

        src_hex = parts[0].strip()
        target_hex_str = parts[1].strip()

        try:
            src_char = chr(int(src_hex, 16))
            target_chars = "".join(chr(int(h, 16)) for h in target_hex_str.split())
        except (ValueError, OverflowError):
            continue

        # Focus on cross-script mappings to ASCII alphanumeric targets (v1 scope)
        if len(target_chars) == 1 and target_chars.isascii() and target_chars.isalnum():
            # Exclude trivial ASCII identity mappings
            if src_char != target_chars and not src_char.isascii():
                mapping[src_char] = target_chars

    return mapping


def generate_code(mapping: dict[str, str], version: str = "16.0.0") -> str:
    """Generate Python source file contents."""
    lines = [
        '"""UTS #39 Confusables mapping table."""',
        "",
        f'CONFUSABLES_VERSION = "{version}"',
        "",
        "# Automatically generated mapping of cross-script lookalikes to ASCII Latin/alphanumeric characters.",
        "CONFUSABLES_MAP: dict[str, str] = {",
    ]

    for src in sorted(mapping.keys(), key=lambda c: ord(c)):
        dst = mapping[src]
        src_repr = repr(src)
        dst_repr = repr(dst)
        hex_code = f"U+{ord(src):04X}"
        lines.append(f"    {src_repr}: {dst_repr},  # {hex_code}")

    lines.append("}\n")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse UTS #39 confusables and build secnorm data table.")
    parser.add_argument(
        "--source",
        default=None,
        help="Local path to confusables.txt. If omitted, downloads from unicode.org.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Target output file path (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--version",
        default="16.0.0",
        help="Unicode data version string (default: 16.0.0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only display mapping count without writing to disk.",
    )

    args = parser.parse_args(argv)

    if args.source is not None:
        source_path = Path(args.source)
        content = source_path.read_text(encoding="utf-8")
    else:
        print(f"Fetching confusables data from {DEFAULT_CONFUSABLES_URL}...")
        try:
            req = urllib.request.Request(DEFAULT_CONFUSABLES_URL, headers={"User-Agent": "secnorm-build-script"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8")
        except Exception as e:
            print(f"Error downloading source: {e}", file=sys.stderr)
            return 1

    mapping = parse_confusables(content)
    print(f"Parsed {len(mapping)} cross-script lookalikes.")

    if args.dry_run:
        print("Dry-run complete. Sample entries:")
        for k in list(mapping.keys())[:10]:
            print(f"  {k!r} (U+{ord(k):04X}) -> {mapping[k]!r}")
        return 0

    code = generate_code(mapping, version=args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(code, encoding="utf-8")
    print(f"Successfully generated {args.output} ({len(mapping)} entries).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
