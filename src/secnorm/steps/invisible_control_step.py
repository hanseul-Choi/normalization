"""Step 2: invisible/control character handling.

See `docs/04-step2-invisible-control-chars.md`. This is one of the
highest-priority steps for the security use case (Tag character smuggling,
bidi override "Trojan Source" attacks, zero-width steganography).

Flag category naming is a concrete design decision not fully pinned down by
the doc's category table (only `zero_width_injection`, `bidi_override`, and
`tag_char_smuggling` are named there); the remaining categories used below
(`control_char`, `bom_injection`, `invisible_spacing`, `private_use_char`,
`unassigned_codepoint`) are this implementation's choice and are recorded in
the doc's "구현 노트" section.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from ..config import InvisibleControlStepConfig
from ..models import Span, SuspicionFlag, Transformation
from ..pipeline import PipelineContext, StepOutput
from ..spanmap import Edit

# ZWSP, ZWNJ, ZWJ, word joiner, soft hyphen
_ZERO_WIDTH = frozenset(chr(c) for c in (0x200B, 0x200C, 0x200D, 0x2060, 0x00AD))
# LRE/RLE/LRO/RLO/PDF, LRI/RLI/FSI/PDI
_BIDI_OVERRIDE = frozenset(chr(c) for c in range(0x202A, 0x202F)) | frozenset(
    chr(c) for c in range(0x2066, 0x206A)
)
_BOM = chr(0xFEFF)
_TAG_CHAR_RANGE = range(0xE0000, 0xE0080)
_VS_RANGE = range(0xFE00, 0xFE10)
_VS_SUPPLEMENT_RANGE = range(0xE0100, 0xE01F0)
# Mongolian vowel separator, Hangul filler, halfwidth Hangul filler
_ABNORMAL_SPACE = frozenset(chr(c) for c in (0x180E, 0x3164, 0xFFA0))


@dataclass(frozen=True)
class _Decision:
    action: str  # "strip" | "keep_flag"
    rule: str
    category: str
    severity: str | None


def _is_emoji_ish(ch: str) -> bool:
    return unicodedata.category(ch) == "So"


def _classify(
    ch: str,
    prev: str | None,
    index: int,
    cfg: InvisibleControlStepConfig,
) -> _Decision | None:
    if ch in cfg.preserve_whitelist:
        return None

    cp = ord(ch)
    cat = unicodedata.category(ch)

    if cat == "Cc":
        if cfg.strip_control:
            return _Decision("strip", "control", "control_char", "medium")
        return None

    if ch == _BOM:
        severity = None if index == 0 else "low"
        return _Decision("strip", "bom", "bom_injection", severity)

    if ch in _ZERO_WIDTH:
        if cfg.strip_zero_width:
            return _Decision("strip", "zero_width", "zero_width_injection", "medium")
        return None

    if ch in _BIDI_OVERRIDE:
        if cfg.strip_bidi_override:
            return _Decision("strip", "bidi_override", "bidi_override", "high")
        return None

    if cp in _TAG_CHAR_RANGE:
        if cfg.strip_tag_chars:
            return _Decision("strip", "tag_char", "tag_char_smuggling", "high")
        return None

    if cp in _VS_SUPPLEMENT_RANGE:
        if cfg.strip_variation_selectors == "none":
            return None
        return _Decision("strip", "variation_selector", "tag_char_smuggling", "high")

    if cp in _VS_RANGE:
        if cfg.strip_variation_selectors == "none":
            return None
        suspicious = prev is None or not _is_emoji_ish(prev)
        if cfg.strip_variation_selectors == "all" or suspicious:
            severity = "high" if suspicious else None
            return _Decision("strip", "variation_selector", "tag_char_smuggling", severity)
        return None

    if ch in _ABNORMAL_SPACE:
        return _Decision("strip", "abnormal_space", "invisible_spacing", "medium")

    if cat == "Co":
        if cfg.private_use_policy == "strip":
            return _Decision("strip", "private_use", "private_use_char", "low")
        if cfg.private_use_policy == "flag":
            return _Decision("keep_flag", "private_use", "private_use_char", "low")
        return None

    if cat == "Cn":
        if cfg.strip_unassigned:
            return _Decision("strip", "unassigned", "unassigned_codepoint", "low")
        return None

    return None


class InvisibleControlStep:
    name = "invisible_control"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        cfg = ctx.config.invisible_control
        text = ctx.text

        out_chars: list[str] = []
        transformations: list[Transformation] = []
        flags: list[SuspicionFlag] = []
        edits: list[Edit] = []

        out_pos = 0
        run_start: int | None = None
        run_rule: str | None = None
        run_category: str | None = None
        run_severity: str | None = None

        def flag_for(span_in_text: Span, category: str, severity: str, detail: str) -> None:
            raw_span = ctx.span_map.to_raw(span_in_text)
            flags.append(
                SuspicionFlag(
                    category=category,
                    severity=severity,
                    step=self.name,
                    span=raw_span,
                    detail=detail,
                )
            )

        def flush(end: int) -> None:
            nonlocal run_start, run_rule, run_category, run_severity
            if run_start is None:
                return
            span_before = Span(run_start, end)
            removed = text[run_start:end]
            span_after = Span(out_pos, out_pos)
            transformations.append(
                Transformation(
                    step=self.name,
                    rule=f"strip_{run_rule}",
                    original=removed,
                    replacement="",
                    span_before=span_before,
                    span_after=span_after,
                )
            )
            edits.append(Edit(span_before, span_after))
            if run_severity is not None:
                flag_for(span_before, run_category, run_severity, run_rule)
            run_start = None
            run_rule = None
            run_category = None
            run_severity = None

        for i, ch in enumerate(text):
            prev = text[i - 1] if i > 0 else None
            decision = _classify(ch, prev, i, cfg)

            if decision is None:
                flush(i)
                out_chars.append(ch)
                out_pos += 1
                continue

            if decision.action == "keep_flag":
                flush(i)
                out_chars.append(ch)
                out_pos += 1
                if decision.severity is not None:
                    flag_for(Span(i, i + 1), decision.category, decision.severity, decision.rule)
                continue

            # action == "strip"
            same_run = run_rule == decision.rule and run_severity == decision.severity
            if not same_run:
                flush(i)
                run_start = i
                run_rule = decision.rule
                run_category = decision.category
                run_severity = decision.severity

        flush(len(text))

        return StepOutput(
            text="".join(out_chars),
            transformations=transformations,
            flags=flags,
            edits=edits,
        )
