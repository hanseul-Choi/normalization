from hypothesis import given, settings, strategies as st

import secnorm
from secnorm.models import Span


@settings(max_examples=100)
@given(st.text())
def test_idempotency_property(text: str):
    """Applying normalization twice produces the same result as applying it once."""
    first = secnorm.normalize(text)
    second = secnorm.normalize(first.normalized_text)
    assert second.normalized_text == first.normalized_text


@settings(max_examples=100)
@given(st.text())
def test_span_map_bounds_property(text: str):
    """to_raw on any sub-span of normalized_text always resolves within [0, len(raw_text)]."""
    result = secnorm.normalize(text)
    norm_len = len(result.normalized_text)
    raw_len = len(result.raw_text)

    # Full text span
    full_raw = result.span_map.to_raw(Span(0, norm_len))
    assert 0 <= full_raw.start <= raw_len
    assert 0 <= full_raw.end <= raw_len
    assert full_raw.start <= full_raw.end

    # Random point checks
    if norm_len > 0:
        mid = norm_len // 2
        mid_raw = result.span_map.to_raw(Span(0, mid))
        assert 0 <= mid_raw.start <= mid_raw.end <= raw_len


@settings(max_examples=100)
@given(st.text())
def test_minimal_preset_idempotency(text: str):
    first = secnorm.normalize(text, preset="minimal")
    second = secnorm.normalize(first.normalized_text, preset="minimal")
    assert second.normalized_text == first.normalized_text


@settings(max_examples=100)
@given(st.text())
def test_nlp_preprocessing_preset_idempotency(text: str):
    first = secnorm.normalize(text, preset="nlp_preprocessing")
    second = secnorm.normalize(first.normalized_text, preset="nlp_preprocessing")
    assert second.normalized_text == first.normalized_text
