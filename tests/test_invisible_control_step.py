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


def test_emoji_zwj_sequences_preserved():
    # 1. Fitzpatrick skin tone + ZWJ + role
    emoji_tech = "👩🏽‍💻"
    output1 = _run(emoji_tech)
    assert output1.text == emoji_tech
    assert not any(f.category == "zero_width_injection" for f in output1.flags)

    # 2. Base + VS16 + ZWJ + gender + VS16
    emoji_write = "✍️‍♀️"
    output2 = _run(emoji_write)
    assert output2.text == emoji_write
    assert not any(f.category == "zero_width_injection" for f in output2.flags)

    # 3. Multi-person family emoji
    emoji_family = "👨‍👩‍👧‍👦"
    output3 = _run(emoji_family)
    assert output3.text == emoji_family
    assert not any(f.category == "zero_width_injection" for f in output3.flags)


def test_text_zwj_smuggling_stripped():
    text = "pass\u200Dword"
    output = _run(text)
    assert output.text == "password"
    assert any(f.category == "zero_width_injection" for f in output.flags)


def test_ascii_sk_with_variation_selector_stripped_and_flagged():
    # Item I: ASCII Sk (^, `) must not be treated as emoji-ish
    # ^ + VS16
    output_caret = _run("^\uFE0F")
    assert output_caret.text == "^"
    assert len(output_caret.flags) == 1
    assert output_caret.flags[0].category == "tag_char_smuggling"
    assert output_caret.flags[0].severity == "high"

    # ` + VS16
    output_backtick = _run("`\uFE0F")
    assert output_backtick.text == "`"
    assert len(output_backtick.flags) == 1
    assert output_backtick.flags[0].category == "tag_char_smuggling"
    assert output_backtick.flags[0].severity == "high"

    # Normal emoji with VS16 should still be preserved without flags
    output_emoji = _run("☀️")  # \u2600\uFE0F
    assert output_emoji.text == "☀️"
    assert output_emoji.flags == []


def test_japanese_ivs_after_cjk_preserved():
    # Item H: Single VS supplement after CJK ideograph should be preserved without flag
    text = "葛\U000E0100"
    output = _run(text)
    assert output.text == text
    assert output.flags == []

    text_mid = "葛\U000E0100城"
    output_mid = _run(text_mid)
    assert output_mid.text == text_mid
    assert output_mid.flags == []

    # Extension B ideograph + IVS
    text_ext = "\U00020000\U000E0100"
    output_ext = _run(text_ext)
    assert output_ext.text == text_ext
    assert output_ext.flags == []


def test_consecutive_ivs_after_cjk_stripped_and_flagged():
    # Item H: 2 or more consecutive VS supplements after CJK are stripped as steganography
    text = "葛\U000E0100\U000E0101"
    output = _run(text)
    assert output.text == "葛"
    assert len(output.flags) == 1
    assert output.flags[0].category == "tag_char_smuggling"
    assert output.flags[0].severity == "high"


def test_ivs_after_non_cjk_or_leading_stripped_and_flagged():
    # Leading VS supplement
    output_lead = _run("\U000E0100")
    assert output_lead.text == ""
    assert any(f.category == "tag_char_smuggling" and f.severity == "high" for f in output_lead.flags)

    # After Latin character
    output_latin = _run("A\U000E0100")
    assert output_latin.text == "A"
    assert any(f.category == "tag_char_smuggling" and f.severity == "high" for f in output_latin.flags)

    # After emoji
    output_emoji = _run("\U0001F600\U000E0100")
    assert output_emoji.text == "\U0001F600"
    assert any(f.category == "tag_char_smuggling" and f.severity == "high" for f in output_emoji.flags)


def test_ivs_strip_variation_selectors_all_and_none():
    # strip_variation_selectors="all": IVS should also be stripped
    cfg_all = NormalizationConfig(
        invisible_control=InvisibleControlStepConfig(strip_variation_selectors="all")
    )
    output_all = _run("葛\U000E0100", config=cfg_all)
    assert output_all.text == "葛"
    assert any(f.category == "tag_char_smuggling" and f.severity == "high" for f in output_all.flags)

    # strip_variation_selectors="none": IVS preserved
    cfg_none = NormalizationConfig(
        invisible_control=InvisibleControlStepConfig(strip_variation_selectors="none")
    )
    output_none = _run("葛\U000E0100", config=cfg_none)
    assert output_none.text == "葛\U000E0100"
    assert output_none.flags == []


def test_ivs_mixed_with_other_controls():
    # When text contains both IVS and ZWSP, only ZWSP should be stripped
    output = _run("葛\U000E0100\u200B城")
    assert output.text == "葛\U000E0100城"
    assert len(output.flags) == 1
    assert output.flags[0].category == "zero_width_injection"


def test_ivs_e2e_preset_stabilization():
    import secnorm

    result = secnorm.normalize("葛\U000E0100城", preset="security_strict")
    assert result.normalized_text == "葛\U000E0100城"
    assert result.flags == []


