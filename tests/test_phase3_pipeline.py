import pytest

import secnorm


def test_all_five_presets_instantiate_successfully():
    presets = [
        "minimal",
        "nlp_preprocessing",
        "security_balanced",
        "security_strict",
        "llm_input_sanitize",
    ]
    for p in presets:
        pipeline = secnorm.Pipeline.from_preset(p)
        assert pipeline.name == p
        res = pipeline.run("Hello world")
        assert res.normalized_text == "Hello world"


def test_security_strict_collapses_separator_in_canonical():
    pipeline = secnorm.Pipeline.from_preset("security_strict")
    res = pipeline.run("f.r.e.e")
    assert res.normalized_text == "free"


def test_llm_input_sanitize_strips_variation_selectors():
    pipeline = secnorm.Pipeline.from_preset("llm_input_sanitize")
    # Emoji variation selector U+FE0F
    text = "❤️\uFE0F test"
    res = pipeline.run(text)
    assert "\uFE0F" not in res.normalized_text


def test_nlp_preprocessing_disables_obfuscation_step():
    pipeline = secnorm.Pipeline.from_preset("nlp_preprocessing")
    # Homoglyph should NOT be converted in nlp_preprocessing
    spoofed = "\u0430dmin"
    res = pipeline.run(spoofed)
    assert "\u0430" in res.normalized_text


def test_unknown_preset_raises_value_error():
    with pytest.raises(ValueError):
        secnorm.build_preset("unknown_preset_foo")
