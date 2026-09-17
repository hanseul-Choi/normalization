"""Latency benchmark tests across presets and text lengths (`docs/12-testing-strategy.md` §5)."""

import pytest
import secnorm

TEXT_30 = "Hello world! Check аpple.com!!"
TEXT_200 = (
    "Security analysis of adversarial inputs: http://example.com/login?u=admin. "
    "Testing for homoglyphs like 'pаypal' and zero-width injections \u200bhidden payload. "
    "Repeated letters like 'coooooool' and extra spaces    are normalized."
)
TEXT_2000 = (TEXT_200 + "\n\n") * 8


@pytest.mark.parametrize("length_name, text", [
    ("30chars", TEXT_30),
    ("200chars", TEXT_200),
    ("2000chars", TEXT_2000),
])
@pytest.mark.parametrize("preset", [
    "minimal",
    "nlp_preprocessing",
    "security_balanced",
    "security_strict",
    "llm_input_sanitize",
])
def test_benchmark_presets(benchmark, length_name: str, text: str, preset: str):
    """Measure single-text normalization latency across preset and text length combinations."""
    pipeline = secnorm.Pipeline.from_preset(preset)
    result = benchmark(pipeline.run, text)
    assert result.normalized_text is not None
