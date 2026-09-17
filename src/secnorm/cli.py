"""Command-line interface for secnorm (`docs/10-api-design.md`, `docs/13-roadmap.md`)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
        help="Input text to normalize. If omitted, reads from --input or standard input (stdin).",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=None,
        help="Path to input file to normalize line-by-line.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Path to output file (default: print to standard output).",
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
        help="Output full NormalizationResult as a formatted JSON object (single input mode).",
    )
    parser.add_argument(
        "--format",
        choices=["text", "jsonl"],
        default="text",
        help="Output format for streaming/batch line processing (default: text).",
    )
    parser.add_argument(
        "--no-raw",
        action="store_true",
        help="Exclude raw_text from JSON output for sensitive data logging.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start lightweight HTTP REST API daemon.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface for HTTP daemon (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP daemon (default: 8000).",
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

    # Check for serve command or --serve flag
    if args.serve or args.text == "serve":
        from .server import run_server

        run_server(host=args.host, port=args.port)
        return 0

    # File-to-file batch streaming mode
    if args.input is not None and args.output is not None:
        secnorm.normalize_file(
            input_path=args.input,
            output_path=args.output,
            preset=args.preset,
            format=args.format,
            include_raw_text=not args.no_raw,
        )
        return 0

    # Single text argument provided
    if args.text is not None:
        raw_text = args.text
    elif args.input is not None:
        # File provided with stdout output
        with args.input.open("r", encoding="utf-8") as f:
            for line in f:
                res = secnorm.normalize(line.rstrip("\r\n"), preset=args.preset)
                if args.format == "jsonl" or args.json:
                    print(res.to_json(include_raw_text=not args.no_raw))
                else:
                    print(res.normalized_text)
            return 0
    else:
        if sys.stdin.isatty():
            parser.print_help(sys.stderr)
            return 1
        raw_text = sys.stdin.read()

    result = secnorm.normalize(raw_text, preset=args.preset)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as out:
            if args.json:
                out.write(result.to_json(indent=2, include_raw_text=not args.no_raw) + "\n")
            elif args.format == "jsonl":
                out.write(result.to_json(include_raw_text=not args.no_raw) + "\n")
            else:
                out.write(result.normalized_text + "\n")
        return 0

    if args.json:
        print(result.to_json(indent=2, include_raw_text=not args.no_raw))
    elif args.format == "jsonl":
        print(result.to_json(include_raw_text=not args.no_raw))
    else:
        print(result.normalized_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
