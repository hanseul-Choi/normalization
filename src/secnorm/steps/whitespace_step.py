"""Step 3: whitespace normalization (docs/05-step3-whitespace-normalization.md).

Two design decisions not pinned to a config field in `docs/02-architecture.md`'s
`WhitespaceStepConfig`, recorded here (and in the doc's "구현 노트"):

- Vertical tab (`U+000B`) and form feed (`U+000C`) are mapped to `\n`,
  grouped with the line/paragraph separators rather than plain spaces.
- The whitespace-collapse regexes never match a literal `\t`: when
  `tab_policy="to_space"`, tabs are already turned into spaces before
  collapsing runs, so this is moot; when `tab_policy="keep"`, this is what
  makes "keep" actually mean "leave every tab alone" in both modes, instead
  of only outside `strict` mode's blanket whitespace fold.
- The language-conditional variant of `preserve_ideographic_space` (only
  preserve U+3000 when step 7 detects ja/zh) needs step 7's language
  metadata, which isn't available yet when step 3 runs (`PipelineContext`
  fills `language` only after step 7). That variant is deferred to Phase 2
  alongside the script-ratio prepass (`docs/13-roadmap.md`); only the plain
  boolean flag is implemented here.

The `separator_injection` heuristic (mixed whitespace-type runs within a
word) described in the doc is intentionally not implemented in this step:
the doc itself defers its actual handling to step 6, and Phase 1 is scoped
to steps with no evasion-detection-specific logic (`docs/13-roadmap.md`).
"""

from __future__ import annotations

import re

from ..config import WhitespaceStepConfig
from ..diffutil import diff_edits
from ..models import Transformation
from ..pipeline import PipelineContext, StepOutput

_TO_SPACE_CODEPOINTS = {0x00A0, 0x2007, 0x202F} | set(range(0x2000, 0x200B))
_TO_NEWLINE_CODEPOINTS = {0x2028, 0x2029, 0x000B, 0x000C}
_IDEOGRAPHIC_SPACE_CODEPOINT = 0x3000
_TAB_CODEPOINT = 0x09

_STRICT_COLLAPSE_RE = re.compile(r"[ \n]+")
_STRUCTURAL_SPACE_COLLAPSE_RE = re.compile(r" {2,}")
_STRUCTURAL_NEWLINE_COLLAPSE_RE = re.compile(r"\n{3,}")
_TRIM_CHARS = " \t\n\r"


def _build_table(cfg: WhitespaceStepConfig) -> dict[int, str]:
    table: dict[int, str] = {cp: " " for cp in _TO_SPACE_CODEPOINTS}
    for cp in _TO_NEWLINE_CODEPOINTS:
        table[cp] = "\n"
    if cfg.tab_policy == "to_space":
        table[_TAB_CODEPOINT] = " "
    if not cfg.preserve_ideographic_space:
        table[_IDEOGRAPHIC_SPACE_CODEPOINT] = " "
    return table


class WhitespaceStep:
    name = "whitespace"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        cfg = ctx.config.whitespace
        text = ctx.text

        # Universal-newline normalization: convert CRLF and solitary CR to LF
        normalized_newlines = text.replace("\r\n", "\n").replace("\r", "\n")
        canonical = normalized_newlines.translate(_build_table(cfg))

        if cfg.mode == "strict":
            collapsed = _STRICT_COLLAPSE_RE.sub(" ", canonical)
        else:
            collapsed = _STRUCTURAL_SPACE_COLLAPSE_RE.sub(" ", canonical)
            collapsed = _STRUCTURAL_NEWLINE_COLLAPSE_RE.sub("\n\n", collapsed)

        if cfg.trim_edges:
            collapsed = collapsed.strip(_TRIM_CHARS)

        if collapsed == text:
            return StepOutput(text=text)

        edits, changes = diff_edits(text, collapsed)
        transformations = [
            Transformation(
                step=self.name,
                rule="normalize_whitespace",
                original=original,
                replacement=replacement,
                span_before=span_before,
                span_after=span_after,
            )
            for span_before, span_after, original, replacement in changes
        ]
        return StepOutput(text=collapsed, transformations=transformations, edits=edits)
