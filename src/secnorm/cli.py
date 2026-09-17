"""Command-line interface for secnorm (`docs/10-api-design.md`)."""

from __future__ import annotations

import argparse
import sys

import secnorm
from secnorm.pipeline import PIPELINE_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="secnorm",
        description="Deterministic, audit-friendly text normalization pipeline for security and LLM use cases.",
    )
    parser.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Input text to normalize. If omitted, reads from standard input (stdin).",
    )
    parser.add_argument(
        "-p",
        "--preset",
        default="security_balanced",
        choices=[
            "minimal",
            "nlp_preprocessing",
            "security_balanced",
            "security_strict",
            "llm_input_sanitize",
        ],
        help="Normalization preset to use (default: security_balanced).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full NormalizationResult as a formatted JSON object.",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Exclude raw_text from JSON output for sensitive data logging.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"secnorm {PIPELINE_VERSION}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.text is not None:
        raw_text = args.text
    else:
        if sys.stdin.isatty():
            parser.print_help(sys.stderr)
            return 1
        raw_text = sys.stdin.read()

    result = secnorm.normalize(raw_text, preset=args.preset)

    if args.json:
        print(result.to_json(indent=2, include_raw_text=not args.no_raw))
    else:
        print(result.normalized_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
