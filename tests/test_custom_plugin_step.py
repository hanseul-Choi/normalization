"""Unit tests for custom pipeline step plugins and insertion API (`docs/10-api-design.md`)."""

import pytest
import secnorm
from secnorm import PipelineContext, StepOutput
from secnorm.models import Span, SuspicionFlag, Transformation
from secnorm.spanmap import Edit


class ProfanityMaskStep:
    name = "profanity_mask"

    def __init__(self, bad_word: str = "badword", mask: str = "***") -> None:
        self.bad_word = bad_word
        self.mask = mask

    def apply(self, ctx: PipelineContext) -> StepOutput:
        text = ctx.text
        if self.bad_word not in text:
            return StepOutput(text=text)

        start = text.index(self.bad_word)
        end = start + len(self.bad_word)
        new_text = text[:start] + self.mask + text[end:]

        src_span = Span(start, end)
        dst_span = Span(start, start + len(self.mask))
        edit = Edit(src_span=src_span, dst_span=dst_span)

        raw_span = ctx.span_map.to_raw(src_span)
        flag = SuspicionFlag(
            category="custom_profanity",
            severity="high",
            step=self.name,
            span=raw_span,
            detail=f"masked {self.bad_word}",
        )
        transformation = Transformation(
            step=self.name,
            rule="mask",
            original=self.bad_word,
            replacement=self.mask,
            span_before=src_span,
            span_after=dst_span,
        )

        return StepOutput(
            text=new_text,
            transformations=[transformation],
            flags=[flag],
            edits=[edit],
        )


def test_insert_step_after():
    pipeline = secnorm.Pipeline.from_preset("minimal")
    step = ProfanityMaskStep("badword", "***")
    pipeline.insert_step(step, after="unicode")

    step_names = [s.name for s in pipeline.steps]
    assert step_names == ["unicode", "profanity_mask", "whitespace"]
    assert "profanity_mask" in pipeline.config.enabled_steps

    res = pipeline.run("This is a badword here.")
    assert res.normalized_text == "This is a *** here."
    assert any(f.category == "custom_profanity" for f in res.flags)
    assert any(t.rule == "mask" for t in res.transformations)


def test_insert_step_before():
    pipeline = secnorm.Pipeline.from_preset("minimal")
    step = ProfanityMaskStep("hello", "hi")
    pipeline.insert_step(step, before="unicode")

    step_names = [s.name for s in pipeline.steps]
    assert step_names == ["profanity_mask", "unicode", "whitespace"]

    res = pipeline.run("hello world")
    assert res.normalized_text == "hi world"


def test_insert_step_disabled():
    pipeline = secnorm.Pipeline.from_preset("minimal")
    step = ProfanityMaskStep("badword", "***")
    pipeline.insert_step(step, after="unicode", enabled=False)

    assert "profanity_mask" not in pipeline.config.enabled_steps
    res = pipeline.run("This is a badword here.")
    assert res.normalized_text == "This is a badword here."


def test_replace_step():
    pipeline = secnorm.Pipeline.from_preset("minimal")

    class UpperWhitespaceStep:
        name = "whitespace"

        def apply(self, ctx: PipelineContext) -> StepOutput:
            return StepOutput(text=ctx.text.upper())

    pipeline.replace_step("whitespace", UpperWhitespaceStep())
    res = pipeline.run("hello world")
    assert res.normalized_text == "HELLO WORLD"


def test_insert_step_error_conditions():
    pipeline = secnorm.Pipeline.from_preset("minimal")
    step = ProfanityMaskStep()

    with pytest.raises(ValueError, match="exactly one of"):
        pipeline.insert_step(step, after="unicode", before="whitespace")

    with pytest.raises(ValueError, match="exactly one of"):
        pipeline.insert_step(step)

    with pytest.raises(ValueError, match="no such step"):
        pipeline.insert_step(step, after="non_existent_step")
