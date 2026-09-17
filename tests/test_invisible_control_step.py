from secnorm.config import InvisibleControlStepConfig, NormalizationConfig
from secnorm.models import Span
from secnorm.pipeline import PipelineContext
from secnorm.spanmap import SpanMap
from secnorm.steps import InvisibleControlStep


def _run(text: str, config: NormalizationConfig | None = None, span_map=None):
    config = config or NormalizationConfig()
    span_map = span_map if span_map is not None else SpanMap.identity(len(text))
    ctx = PipelineContext(raw_text=text, text=text, config=config, span_map=span_map)
    return InvisibleControlStep().apply(ctx)


def test_zero_width_space_is_stripped_and_flagged():
    output = _run("무료 배​포")
    assert output.text == "무료 배포"
    assert len(output.flags) == 1
    flag = output.flags[0]
    assert flag.category == "zero_width_injection"
    assert flag.severity == "medium"
    assert flag.span == Span(4, 5)


def test_tag_chars_are_stripped_with_high_severity():
    hidden = chr(0xE0000 + ord("h")) + chr(0xE0000 + ord("i"))
    output = _run("admin" + hidden)
    assert output.text == "admin"
    assert output.flags[0].category == "tag_char_smuggling"
    assert output.flags[0].severity == "high"


def test_bidi_override_stripped_leaves_codepoints_in_original_order():
    output = _run("‮reversed‬")
    assert output.text == "reversed"
    assert all(f.category == "bidi_override" and f.severity == "high" for f in output.flags)
    assert len(output.flags) == 2


def test_leading_bom_removed_silently():
    output = _run("﻿hello")
    assert output.text == "hello"
    assert output.flags == []


def test_mid_string_bom_removed_with_low_flag():
    output = _run("he﻿llo")
    assert output.text == "hello"
    assert output.flags[0].severity == "low"
    assert output.flags[0].category == "bom_injection"


def test_control_char_stripped_with_medium_flag():
    output = _run("a\x01b")
    assert output.text == "ab"
    assert output.flags[0].category == "control_char"
    assert output.flags[0].severity == "medium"


def test_tab_and_newline_are_preserved_by_default():
    output = _run("a\tb\nc")
    assert output.text == "a\tb\nc"
    assert output.transformations == []
    assert output.flags == []


def test_emoji_presentation_selector_kept_silently():
    output = _run("❤️")  # heavy black heart + VS16
    assert output.text == "❤️"
    assert output.flags == []


def test_variation_selector_without_emoji_context_is_suspicious():
    output = _run("a️")
    assert output.text == "a"
    assert output.flags[0].category == "tag_char_smuggling"
    assert output.flags[0].severity == "high"


def test_vs_supplement_always_stripped_and_flagged():
    output = _run("a" + chr(0xE0100))
    assert output.text == "a"
    assert output.flags[0].category == "tag_char_smuggling"


def test_private_use_default_policy_flags_without_stripping():
    output = _run("ab")
    assert output.text == "ab"
    assert output.flags[0].category == "private_use_char"
    assert output.flags[0].severity == "low"


def test_private_use_strip_policy_removes_char():
    config = NormalizationConfig(invisible_control=InvisibleControlStepConfig(private_use_policy="strip"))
    output = _run("ab", config=config)
    assert output.text == "ab"


def test_private_use_keep_policy_is_silent():
    config = NormalizationConfig(invisible_control=InvisibleControlStepConfig(private_use_policy="keep"))
    output = _run("ab", config=config)
    assert output.text == "ab"
    assert output.flags == []


def test_unassigned_codepoint_stripped_with_low_flag():
    output = _run("a\U0010fffeb")
    assert output.text == "ab"
    assert output.flags[0].category == "unassigned_codepoint"
    assert output.flags[0].severity == "low"


def test_hangul_filler_stripped_with_medium_flag():
    output = _run("aㅤb")
    assert output.text == "ab"
    assert output.flags[0].category == "invisible_spacing"
    assert output.flags[0].severity == "medium"


def test_consecutive_same_rule_run_merges_into_one_transformation():
    output = _run("a​​b")
    assert len(output.transformations) == 1
    assert output.transformations[0].span_before == Span(1, 3)


def test_flag_span_is_expressed_in_raw_text_coordinates():
    # Simulate this step running after an earlier step already shrank the text
    # by one char at the start, so ctx.text differs from raw_text.
    raw_text = "Xa​b"
    span_map = SpanMap.identity(len(raw_text)).compose(
        [__import__("secnorm").Edit(Span(0, 1), Span(0, 0))]
    )
    output = _run("a​b", config=None, span_map=span_map)
    assert output.flags[0].span == Span(2, 3)


def test_disabling_strip_control_leaves_control_chars_untouched():
    config = NormalizationConfig(invisible_control=InvisibleControlStepConfig(strip_control=False))
    output = _run("a\x01b", config=config)
    assert output.text == "a\x01b"
    assert output.flags == []
