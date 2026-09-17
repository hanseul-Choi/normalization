"""Shared diff helper for pipeline steps.

Several steps (unicode normalization, whitespace normalization, ...) transform
the whole input text at once via a library call or a translate table, rather
than tracking edits as they go. This helper recovers the changed regions
after the fact so steps can still emit `Transformation`/`Edit` objects per
`docs/02-architecture.md` ("변경된 구간 단위로 묶어서 기록").

Uses `difflib.SequenceMatcher`, which is quadratic in the worst case; this is
acceptable given the real-time single-message scope (`docs/01-overview.md`)
but would need revisiting for large batch inputs (`docs/13-roadmap.md`, v1
범위 밖).
"""

from __future__ import annotations

import difflib

from .models import Span
from .spanmap import Edit


def diff_edits(old: str, new: str) -> tuple[list[Edit], list[tuple[Span, Span, str, str]]]:
    """Compute edits and (span_before, span_after, original, replacement) tuples.

    Unchanged regions are omitted entirely (identity, no edit needed).
    """
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    edits: list[Edit] = []
    changes: list[tuple[Span, Span, str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        src = Span(i1, i2)
        dst = Span(j1, j2)
        edits.append(Edit(src, dst))
        changes.append((src, dst, old[i1:i2], new[j1:j2]))
    return edits, changes
