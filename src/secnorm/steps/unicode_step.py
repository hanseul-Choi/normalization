"""Step 1: Unicode normalization (docs/03-step1-unicode-normalization.md)."""

from __future__ import annotations

import unicodedata

from ..diffutil import diff_edits
from ..models import Transformation
from ..pipeline import PipelineContext, StepOutput


class UnicodeStep:
    name = "unicode"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        cfg = ctx.config.unicode
        text = ctx.text
        normalized = unicodedata.normalize(cfg.form, text)

        if normalized == text:
            return StepOutput(text=text)

        edits, changes = diff_edits(text, normalized)
        transformations = [
            Transformation(
                step=self.name,
                rule=f"normalize_{cfg.form}",
                original=original,
                replacement=replacement,
                span_before=span_before,
                span_after=span_after,
            )
            for span_before, span_after, original, replacement in changes
        ]
        return StepOutput(text=normalized, transformations=transformations, edits=edits)
