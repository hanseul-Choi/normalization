from secnorm.config import NormalizationConfig
from secnorm.models import Span
from secnorm.pipeline import NormalizationPipeline
from secnorm.presets import build_preset
from secnorm.steps import EncodingEscapingStep, InvisibleControlStep, UnicodeStep, WhitespaceStep


def _full_pipeline() -> NormalizationPipeline:
    return NormalizationPipeline(
        [UnicodeStep(), InvisibleControlStep(), WhitespaceStep(), EncodingEscapingStep()],
        NormalizationConfig(),
        name="phase1",
    )


def test_steps_compose_and_span_map_resolves_to_raw_text():
    pipeline = _full_pipeline()
    raw = "무료   배​포 이벤트  Ａｄｍｉｎ"
    result = pipeline.run(raw)
    assert result.raw_text == raw
    assert "​" not in result.normalized_text  # zero-width space gone
    assert "Ａ" not in result.normalized_text  # fullwidth folded
    assert result.span_map.to_raw(Span(0, len(result.normalized_text))).end == len(raw)


def test_idempotency_across_all_four_steps():
    pipeline = _full_pipeline()
    cases = [
        "Ａｄｍｉｎ 배​포 무료   상담",
        "AT&amp;T https://example.com/%ED%95%9C",
        "안\\uB155 반갑습니다",
    ]
    for text in cases:
        once = pipeline.run(text).normalized_text
        twice = pipeline.run(once).normalized_text
        assert once == twice


def test_disabling_a_step_skips_it():
    pipeline = _full_pipeline()
    pipeline.disable("whitespace")
    result = pipeline.run("a   b")
    assert result.normalized_text == "a   b"


def test_minimal_preset_only_runs_unicode_nfc_and_whitespace_trim():
    pipeline = build_preset("minimal")
    result = pipeline.run("  Ａｄｍｉｎ  ")
    # NFC (not NFKC) leaves fullwidth compatibility chars alone.
    assert result.normalized_text == "Ａｄｍｉｎ"


def test_unimplemented_presets_raise_not_implemented():
    import pytest

    for name in ("security_strict", "llm_input_sanitize", "nlp_preprocessing"):
        with pytest.raises(NotImplementedError):
            build_preset(name)


def test_security_balanced_preset_reduced_runs_all_four_steps():
    import secnorm

    pipeline = secnorm.Pipeline.from_preset("security_balanced")
    raw = "  Ａｄｍｉｎ &amp; 배​포  "
    result = pipeline.run(raw)
    assert result.normalized_text == "Admin & 배포"
    assert result.config_name == "security_balanced"
    # Should have flagged zero-width space
    assert any(f.category == "zero_width_injection" for f in result.flags)


def test_top_level_normalize_api():
    import secnorm

    # Default preset is security_balanced
    result = secnorm.normalize("  Ａｄｍｉｎ &amp; 배​포  ")
    assert result.normalized_text == "Admin & 배포"

    # Minimal preset
    result_min = secnorm.normalize("  Ａｄｍｉｎ  ", preset="minimal")
    assert result_min.normalized_text == "Ａｄｍｉｎ"


def test_top_level_normalize_batch_api():
    import secnorm

    texts = ["  Ａｄｍｉｎ  ", "  테​스트  "]
    results = secnorm.normalize_batch(texts, preset="security_balanced", n_jobs=2)
    assert len(results) == 2
    assert results[0].normalized_text == "Admin"
    assert results[1].normalized_text == "테스트"


def test_pipeline_instantiation_from_config():
    import secnorm

    cfg = secnorm.NormalizationConfig(enabled_steps={"unicode"})
    pipeline = secnorm.Pipeline(config=cfg)
    result = pipeline.run("  Ａｄｍｉｎ  ")
    # Only unicode NFKC ran, whitespace was not trimmed/collapsed
    assert result.normalized_text == "  Admin  "
