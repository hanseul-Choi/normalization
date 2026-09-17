import pytest

from secnorm.config import NormalizationConfig, ObfuscationStepConfig
from secnorm.models import Span
from secnorm.pipeline import PipelineContext
from secnorm.spanmap import SpanMap
from secnorm.steps.obfuscation_step import ObfuscationStep


def _ctx(text: str, cfg: ObfuscationStepConfig | None = None) -> PipelineContext:
    config = NormalizationConfig()
    if cfg is not None:
        config.obfuscation = cfg
    return PipelineContext(
        raw_text=text,
        text=text,
        config=config,
        span_map=SpanMap.identity(len(text)),
    )


def test_homoglyph_normalization_in_canonical():
    step = ObfuscationStep()
    # Cyrillic small 'a' (U+0430) mixed with Latin 'dmin'
    spoofed = "\u0430dmin"
    out = step.apply(_ctx(spoofed))

    assert out.text == "admin"
    assert len(out.transformations) == 1
    assert out.transformations[0].rule == "homoglyph_normalize"
    assert len(out.flags) == 1
    assert out.flags[0].category == "homoglyph"
    assert out.flags[0].severity == "high"


def test_single_script_foreign_text_is_not_homoglyph_normalized():
    step = ObfuscationStep()
    # Pure Russian Cyrillic word
    russian = "Привет"
    out = step.apply(_ctx(russian))

    assert out.text == russian
    assert len(out.transformations) == 0
    assert len(out.flags) == 0


def test_separator_injection_aggressive_variant():
    step = ObfuscationStep()
    text = "f r e e   m o n e y"
    out = step.apply(_ctx(text))

    # Canonical text is preserved
    assert out.text == text
    # Aggressive variant collapses delimiters
    assert "aggressive" in out.variants
    assert out.variants["aggressive"] == "free money"
    assert any(f.category == "separator_injection" for f in out.flags)


def test_separator_injection_collapse_in_canonical_when_configured():
    cfg = ObfuscationStepConfig(separator_injection_collapse_in_canonical=True)
    step = ObfuscationStep()
    text = "f.r.e.e"
    out = step.apply(_ctx(text, cfg=cfg))

    assert out.text == "free"
    assert len(out.transformations) >= 1
    assert out.transformations[0].rule == "collapse_separator"


def test_separator_injection_collapse_in_canonical_with_dictionary():
    cfg = ObfuscationStepConfig(dictionary=frozenset({"free"}))
    step = ObfuscationStep()
    text = "f-r-e-e"
    out = step.apply(_ctx(text, cfg=cfg))

    assert out.text == "free"


def test_leetspeak_substitution_in_aggressive_variant():
    step = ObfuscationStep()
    text = "h3ll0 w0rld"
    out = step.apply(_ctx(text))

    # Canonical is preserved
    assert out.text == text
    assert "aggressive" in out.variants
    assert out.variants["aggressive"] == "hello world"
    assert any(f.category == "leetspeak" for f in out.flags)


def test_encoded_payload_detection():
    step = ObfuscationStep()
    # 24 chars Base64: "dGhpcyBpcyBhIHRlc3Qgc3Ry"
    text = "Check this payload: dGhpcyBpcyBhIHRlc3Qgc3Ry now"
    out = step.apply(_ctx(text))

    assert out.text == text
    assert any(f.category == "encoded_payload" for f in out.flags)


def test_decode_and_recurse():
    import base64

    cfg = ObfuscationStepConfig(decode_and_recurse=True)
    step = ObfuscationStep()

    # Payload contains homoglyph: "\u0430dmin" encoded in base64
    inner_payload = "\u0430dmin"
    b64_str = base64.b64encode(inner_payload.encode("utf-8")).decode("ascii")
    # Make sure it meets min length 16 with padding if needed
    padded_b64 = "YWJjZGVmZ2hpams="  # 16 chars

    text = f"prefix {padded_b64} suffix"
    out = step.apply(_ctx(text, cfg=cfg))

    assert any(f.category == "encoded_payload" for f in out.flags)
