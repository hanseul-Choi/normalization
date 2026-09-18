"""Streaming and file I/O normalization pipeline (`docs/10-api-design.md`, `docs/13-roadmap.md`)."""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from .config import NormalizationConfig
from .models import NormalizationResult
from .presets import build_preset


def _chunk_iterable(iterable: Iterable[str], size: int) -> Iterator[list[str]]:
    it = iter(iterable)
    while True:
        chunk = list(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk


def normalize_stream(
    texts: Iterable[str],
    preset: str = "security_balanced",
    *,
    config: NormalizationConfig | None = None,
    chunk_size: int = 1000,
    n_jobs: int = 1,
) -> Iterator[NormalizationResult]:
    """Yield NormalizationResults lazily from an iterable of texts.

    Parameters
    ----------
    texts : Iterable[str]
        Stream/iterable of input texts.
    preset : str
        Preset name to use (default: "security_balanced").
    config : NormalizationConfig | None
        Optional custom config override.
    chunk_size : int
        Number of items per batch chunk (default: 1000).
    n_jobs : int
        Number of worker threads (default: 1).

    Yields
    ------
    NormalizationResult
        Deterministic normalization result for each input text.
    """
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be positive, got {chunk_size}")

    pipeline = build_preset(preset)
    if config is not None:
        pipeline.config = config

    if n_jobs <= 1:
        for text in texts:
            yield pipeline.run(text)
    else:
        with ThreadPoolExecutor(max_workers=n_jobs) as executor:
            for chunk in _chunk_iterable(texts, chunk_size):
                for res in executor.map(pipeline.run, chunk):
                    yield res


def normalize_file(
    input_path: str | Path,
    output_path: str | Path,
    preset: str = "security_balanced",
    *,
    config: NormalizationConfig | None = None,
    format: Literal["text", "jsonl"] = "text",
    chunk_size: int = 1000,
    n_jobs: int = 1,
    include_raw_text: bool = True,
    include_risk: bool = False,
) -> int:
    """Normalize lines from an input file and write them to an output file.

    Parameters
    ----------
    input_path : str | Path
        Path to input text file.
    output_path : str | Path
        Path to destination output file.
    preset : str
        Preset name (default: "security_balanced").
    config : NormalizationConfig | None
        Optional config override.
    format : "text" | "jsonl"
        Output format. "text" writes normalized_text lines, "jsonl" writes full JSON lines.
    chunk_size : int
        Chunk batch size for processing.
    n_jobs : int
        Worker threads for parallel processing.
    include_raw_text : bool
        Whether to include raw_text in JSON lines (default True).
    include_risk : bool
        Whether to include risk scoring assessment in JSON lines (default False).

    Returns
    -------
    int
        Count of processed lines.
    """
    if format not in ("text", "jsonl"):
        raise ValueError(f"Invalid format {format!r}, must be 'text' or 'jsonl'")

    input_file = Path(input_path)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    def line_generator() -> Iterator[str]:
        with input_file.open("r", encoding="utf-8") as f:
            for line in f:
                yield line.rstrip("\r\n")

    count = 0
    stream = normalize_stream(
        line_generator(),
        preset=preset,
        config=config,
        chunk_size=chunk_size,
        n_jobs=n_jobs,
    )

    with output_file.open("w", encoding="utf-8") as out:
        for result in stream:
            count += 1
            if format == "jsonl":
                out.write(
                    result.to_json(
                        include_raw_text=include_raw_text,
                        include_risk=include_risk,
                    )
                    + "\n"
                )
            else:
                out.write(result.normalized_text + "\n")

    return count
