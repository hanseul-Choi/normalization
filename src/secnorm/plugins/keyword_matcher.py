"""Keyword matcher plugin step (`docs/10-api-design.md`, `docs/13-roadmap.md`)."""

from __future__ import annotations

from collections.abc import Iterable

from ..models import Severity, Span, SuspicionFlag, Transformation
from ..pipeline import PipelineContext, StepOutput
from ..spanmap import Edit
from .trie import Trie


class KeywordMatcherStep:
    """Plugin step that scans text against a blocklist/dictionary of keywords."""

    name = "keyword_matcher"

    def __init__(
        self,
        keywords: Iterable[str],
        *,
        case_sensitive: bool = False,
        severity: Severity = "high",
        category: str = "keyword_match",
        mask: str | None = None,
        name: str = "keyword_matcher",
    ) -> None:
        self.name = name
        self.case_sensitive = case_sensitive
        self.severity = severity
        self.category = category
        self.mask = mask

        clean_keywords = [k if case_sensitive else k.lower() for k in keywords if k]
        self.trie = Trie(clean_keywords)

    def apply(self, ctx: PipelineContext) -> StepOutput:
        text = ctx.text
        matches = self.trie.find_all(text, case_sensitive=self.case_sensitive)

        if not matches:
            return StepOutput(text=text)

        flags: list[SuspicionFlag] = []
        transformations: list[Transformation] = []
        edits: list[Edit] = []

        # Remove overlapping matches by selecting non-overlapping intervals
        matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
        filtered_matches: list[tuple[int, int, str]] = []
        last_end = -1
        for start, end, word in matches:
            if start >= last_end:
                filtered_matches.append((start, end, word))
                last_end = end

        new_text = text
        if self.mask is not None:
            # Process in reverse order to preserve string indices
            for start, end, word in reversed(filtered_matches):
                src_span = Span(start, end)
                dst_span = Span(start, start + len(self.mask))
                raw_span = ctx.span_map.to_raw(src_span)

                flags.append(
                    SuspicionFlag(
                        category=self.category,
                        severity=self.severity,
                        step=self.name,
                        span=raw_span,
                        detail=f"matched keyword: {word}",
                    )
                )
                transformations.append(
                    Transformation(
                        step=self.name,
                        rule="mask_keyword",
                        original=text[start:end],
                        replacement=self.mask,
                        span_before=src_span,
                        span_after=dst_span,
                    )
                )
                edits.append(Edit(src_span=src_span, dst_span=dst_span))
                new_text = new_text[:start] + self.mask + new_text[end:]
            # Reverse back to natural document order
            flags.reverse()
            transformations.reverse()
            edits.reverse()
        else:
            for start, end, word in filtered_matches:
                src_span = Span(start, end)
                raw_span = ctx.span_map.to_raw(src_span)
                flags.append(
                    SuspicionFlag(
                        category=self.category,
                        severity=self.severity,
                        step=self.name,
                        span=raw_span,
                        detail=f"matched keyword: {word}",
                    )
                )

        return StepOutput(
            text=new_text,
            transformations=transformations,
            flags=flags,
            edits=edits,
        )
