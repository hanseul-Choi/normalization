import time
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


@settings(max_examples=50)
@given(st.text())
def test_security_strict_idempotency(text: str):
    first = secnorm.normalize(text, preset="security_strict")
    second = secnorm.normalize(first.normalized_text, preset="security_strict")
    assert second.normalized_text == first.normalized_text


@settings(max_examples=50)
@given(st.text())
def test_llm_input_sanitize_idempotency(text: str):
    first = secnorm.normalize(text, preset="llm_input_sanitize")
    second = secnorm.normalize(first.normalized_text, preset="llm_input_sanitize")
    assert second.normalized_text == first.normalized_text


@settings(max_examples=100)
@given(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126)))
def test_non_corruption_plain_text(text: str):
    """Clean plain ASCII text with standard punctuation should retain non-whitespace content."""
    res = secnorm.normalize(text, preset="minimal")
    # Non-whitespace characters should be preserved exactly under minimal preset
    raw_chars = [c for c in text if not c.isspace()]
    norm_chars = [c for c in res.normalized_text if not c.isspace()]
    assert norm_chars == raw_chars


@settings(max_examples=50)
@given(st.lists(st.integers(min_value=0, max_value=0x10FFFF), min_size=1, max_size=100))
def test_total_function_arbitrary_codepoints(codepoints: list[int]):
    """Normalization pipeline must be a total function and never raise on arbitrary unicode codepoints."""
    chars = []
    for cp in codepoints:
        try:
            chars.append(chr(cp))
        except (ValueError, OverflowError):
            continue
    input_text = "".join(chars)
    for preset in ("minimal", "security_balanced", "security_strict"):
        result = secnorm.normalize(input_text, preset=preset)
        assert isinstance(result.normalized_text, str)
        assert isinstance(result.flags, list)


@settings(max_examples=30)
@given(st.text(min_size=500, max_size=2000))
def test_dos_resistance_linear_time(text: str):
    """Heavy repetitive or complex inputs should complete promptly without exponential slowdown."""
    start = time.perf_counter()
    secnorm.normalize(text, preset="security_balanced")
    elapsed = time.perf_counter() - start
    # 2000 chars should comfortably process within 0.5s in pure Python on CPU
    assert elapsed < 0.5


def test_fixpoint_escaped_zero_width_space():
    # Literal unicode escape for zero-width space
    raw = "hello\\u200bworld"
    res = secnorm.normalize(raw, preset="security_balanced")
    # In one call, \u200b is decoded to ZWSP, then ZWSP is stripped
    assert res.normalized_text == "helloworld"
    # Both flags are present
    categories = [f.category for f in res.flags]
    assert "encoded_payload" in categories
    assert "zero_width_injection" in categories
    # The zero_width_injection flag's span maps back to the \u200b in raw_text
    zw_flag = next(f for f in res.flags if f.category == "zero_width_injection")
    assert raw[zw_flag.span.start : zw_flag.span.end] == "\\u200b"


def test_fixpoint_double_url_encoding():
    raw = "%253Cscript%253E"
    res = secnorm.normalize(raw, preset="security_strict")
    # In one call, %253C -> %3C -> <script>
    assert res.normalized_text == "<script>"
    # Idempotent: normalizing again yields the exact same normalized_text
    res2 = secnorm.normalize(res.normalized_text, preset="security_strict")
    assert res2.normalized_text == res.normalized_text

