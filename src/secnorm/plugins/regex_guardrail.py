"""Regex-based guardrail plugin step (`docs/10-api-design.md`, `docs/13-roadmap.md`)."""

from __future__ import annotations

import re
from typing import Pattern

from ..models import Severity, Span, SuspicionFlag, Transformation
from ..pipeline import PipelineContext, StepOutput
from ..spanmap import Edit


class RegexGuardrailStep:
    """Plugin step that matches configurable regular expression patterns and emits suspicion flags."""

    name = "regex_guardrail"

    def __init__(
        self,
        patterns: dict[str, str | Pattern[str]],
        *,
        severity: Severity = "medium",
        mask: str | None = None,
        name: str = "regex_guardrail",
    ) -> None:
        self.name = name
        self.severity = severity
        self.mask = mask
        self.patterns: dict[str, Pattern[str]] = {
            k: re.compile(v) if isinstance(v, str) else v
            for k, v in patterns.items()
        }

    def apply(self, ctx: PipelineContext) -> StepOutput:
        text = ctx.text
        flags: list[SuspicionFlag] = []
        transformations: list[Transformation] = []
        edits: list[Edit] = []

        # Collect all matches across all patterns
        all_matches: list[tuple[int, int, str, str]] = []  # (start, end, pattern_name, matched_text)
        for pattern_name, regex in self.patterns.items():
            for m in regex.finditer(text):
                all_matches.append((m.start(), m.end(), pattern_name, m.group(0)))

        if not all_matches:
            return StepOutput(text=text)

        # Sort and eliminate overlaps
        all_matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
        filtered_matches: list[tuple[int, int, str, str]] = []
        last_end = -1
        for start, end, name, matched_str in all_matches:
            if start >= last_end:
                filtered_matches.append((start, end, name, matched_str))
                last_end = end

        new_text = text
        if self.mask is not None:
            for start, end, name, matched_str in reversed(filtered_matches):
                src_span = Span(start, end)
                dst_span = Span(start, start + len(self.mask))
                raw_span = ctx.span_map.to_raw(src_span)

                flags.append(
                    SuspicionFlag(
                        category=f"regex_{name}",
                        severity=self.severity,
                        step=self.name,
                        span=raw_span,
                        detail=f"matched regex: {name}",
                    )
                )
                transformations.append(
                    Transformation(
                        step=self.name,
                        rule=f"mask_{name}",
                        original=matched_str,
                        replacement=self.mask,
                        span_before=src_span,
                        span_after=dst_span,
                    )
                )
                edits.append(Edit(src_span=src_span, dst_span=dst_span))
                new_text = new_text[:start] + self.mask + new_text[end:]

            flags.reverse()
            transformations.reverse()
            edits.reverse()
        else:
            for start, end, name, _ in filtered_matches:
                src_span = Span(start, end)
                raw_span = ctx.span_map.to_raw(src_span)
                flags.append(
                    SuspicionFlag(
                        category=f"regex_{name}",
                        severity=self.severity,
                        step=self.name,
                        span=raw_span,
                        detail=f"matched regex: {name}",
                    )
                )

        return StepOutput(
            text=new_text,
            transformations=transformations,
            flags=flags,
            edits=edits,
        )
