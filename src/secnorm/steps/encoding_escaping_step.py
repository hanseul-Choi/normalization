"""Step 4: encoding / escaping normalization (docs/06-step4-encoding-escaping.md).

This step chains several sub-transforms (HTML entity decode -> URL
percent-decode -> Unicode escape decode -> optional mojibake repair)
internally. Each sub-transform is diffed against the *previous* sub-stage's
output and folded into a scratch `SpanMap` (`_local_map`) so that, by the
end, every recorded change can be expressed in `Transformation`/`Edit`
coordinates relative to this step's actual input/output (`docs/02-architecture.md`:
span_before/span_after are "이 단계 입력/출력 기준 좌표", not an intermediate
scratch stage). `SuspicionFlag.span` additionally goes through
`ctx.span_map.to_raw()` to land in `raw_text` coordinates as required by the
same doc.

Known limitation: if two sub-transforms happen to change the exact same
original region twice (e.g. a decoded HTML entity that itself looks like a
URL-encoded sequence), the emitted `Edit` list dedupes by original span and
keeps the final mapped output span; genuinely *overlapping-but-not-identical*
double edits are not merged. This is expected to be rare enough in practice
to defer proper interval merging past Phase 1.

Mojibake repair (4-4) is optional (default off) and best-effort via the
optional `ftfy` dependency (`docs/11-dependencies.md`); if `mojibake_repair`
is enabled but `ftfy` isn't installed, this step no-ops for that sub-feature
rather than raising (steps must be total functions). `ftfy` doesn't expose a
single confidence score the way the doc's "신뢰도 점수" phrasing implies --
`metadata["ftfy_operations"]` instead records the list of repair operations
`ftfy.fix_and_explain` reports.
"""

from __future__ import annotations

import html
import re
import unicodedata
from urllib.parse import unquote

from ..diffutil import diff_edits
from ..models import Span, SuspicionFlag, Transformation
from ..pipeline import PipelineContext, StepOutput
from ..spanmap import Edit, SpanMap

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_PERCENT_ENCODED_RE = re.compile(r"%[0-9A-Fa-f]{2}")
_UNICODE_ESCAPE_RE = re.compile(
    r"\\u([0-9A-Fa-f]{4})|\\U([0-9A-Fa-f]{8})|\\x([0-9A-Fa-f]{2})|\\N\{([^{}]+)\}"
)


def _decode_urls(text: str, mode: str) -> tuple[str, list[Span]]:
    """Returns (decoded_text, stray %XX spans in `text`, i.e. pre-decode coords)."""
    if mode == "off":
        return text, []
    if mode == "always":
        return unquote(text), []

    url_spans = [m.span() for m in _URL_RE.finditer(text)]
    decoded = _URL_RE.sub(lambda m: unquote(m.group(0)), text)
    stray_spans = [
        Span(*m.span())
        for m in _PERCENT_ENCODED_RE.finditer(text)
        if not any(s <= m.start() and m.end() <= e for s, e in url_spans)
    ]
    return decoded, stray_spans


def _decode_unicode_escapes(text: str) -> str:
    def _replace(m: re.Match[str]) -> str:
        hex4, hex8, hex2, name = m.groups()
        try:
            if hex4 is not None:
                return chr(int(hex4, 16))
            if hex8 is not None:
                return chr(int(hex8, 16))
            if hex2 is not None:
                return chr(int(hex2, 16))
            return unicodedata.lookup(name)
        except (ValueError, KeyError):
            return m.group(0)

    return _UNICODE_ESCAPE_RE.sub(_replace, text)


class EncodingEscapingStep:
    name = "encoding_escaping"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        cfg = ctx.config.encoding_escaping
        original_text = ctx.text
        current = original_text
        local_map = SpanMap.identity(len(current))

        pending: list[tuple[str, Span, dict]] = []
        flags: list[SuspicionFlag] = []

        def record_flags(spans_local: list[Span], category: str, severity: str, detail: str) -> None:
            for span_local in spans_local:
                original_span = local_map.to_raw(span_local)
                flags.append(
                    SuspicionFlag(
                        category=category,
                        severity=severity,
                        step=self.name,
                        span=ctx.span_map.to_raw(original_span),
                        detail=detail,
                    )
                )

        def record_changes(new_text: str, rule: str, metadata: dict | None = None) -> None:
            nonlocal current, local_map
            if new_text == current:
                return
            edits, changes = diff_edits(current, new_text)
            for span_before_local, _span_after_local, _orig, _repl in changes:
                original_span = local_map.to_raw(span_before_local)
                pending.append((rule, original_span, metadata or {}))
            local_map = local_map.compose(edits)
            current = new_text

        if cfg.decode_html_entities:
            record_changes(html.unescape(current), "decode_html_entity")

        if cfg.decode_url_encoding != "off":
            decoded, stray_spans = _decode_urls(current, cfg.decode_url_encoding)
            record_flags(stray_spans, "encoded_payload", "low", "percent_encoding_outside_url")
            record_changes(decoded, "decode_url_percent_encoding")

        if cfg.unicode_escape_policy == "flag_only":
            matched_local = [Span(*m.span()) for m in _UNICODE_ESCAPE_RE.finditer(current)]
            record_flags(matched_local, "encoded_payload", "medium", "unicode_escape_sequence")
        elif cfg.unicode_escape_policy == "decode_and_flag":
            matched_local = [Span(*m.span()) for m in _UNICODE_ESCAPE_RE.finditer(current)]
            record_flags(matched_local, "encoded_payload", "medium", "unicode_escape_sequence")
            record_changes(_decode_unicode_escapes(current), "decode_unicode_escape")

        if cfg.mojibake_repair:
            try:
                import ftfy
            except ImportError:
                ftfy = None
            if ftfy is not None:
                fixed, explanation = ftfy.fix_and_explain(current)
                record_changes(
                    fixed,
                    "mojibake_repair",
                    {"ftfy_operations": [op for op, *_ in explanation]},
                )

        if current == original_text:
            return StepOutput(text=original_text, flags=flags)

        distinct_spans: dict[tuple[int, int], Span] = {}
        for _rule, original_span, _metadata in pending:
            distinct_spans.setdefault((original_span.start, original_span.end), original_span)

        edits = [
            Edit(span, local_map.to_normalized(span) or Span(0, 0))
            for span in distinct_spans.values()
        ]

        transformations = [
            Transformation(
                step=self.name,
                rule=rule,
                original=original_text[original_span.start : original_span.end],
                replacement=current[final_span.start : final_span.end],
                span_before=original_span,
                span_after=final_span,
                metadata=metadata,
            )
            for rule, original_span, metadata in pending
            for final_span in [local_map.to_normalized(original_span) or Span(0, 0)]
        ]

        return StepOutput(text=current, transformations=transformations, flags=flags, edits=edits)
