import pytest

import secnorm
from secnorm.models import Span


def test_full_phase2_security_balanced_pipeline():
    raw = "  Ａｄｍｉｎ &amp; 배​포  coooooool ㅋㅋㅋㅋㅋ  "
    result = secnorm.normalize(raw, preset="security_balanced")

    # Step 1: fullwidth Admin -> Admin
    # Step 2: zero-width in 배포 stripped
    # Step 3: whitespace normalized to single space, trimmed
    # Step 4: &amp; -> &
    # Step 5: coooooool -> cool, ㅋㅋㅋㅋㅋ -> ㅋㅋㅋ (capped to 3)
    # Step 7: language metadata populated
    import unicodedata

    expected = unicodedata.normalize("NFKC", "Admin & 배포 cool ㅋㅋㅋ")
    assert result.normalized_text == expected

    # Flags check
    categories = [f.category for f in result.flags]
    assert "zero_width_injection" in categories
    assert "excessive_repetition" in categories

    # Language metadata check
    assert result.language.primary_language == "ko"
    assert result.language.is_mixed_script is True  # Latin ("Admin", "cool") + Hangul ("배포", "ㅋㅋㅋ")
    assert result.language.structural.direction == "ltr"


def test_nlp_preprocessing_preset():
    pipeline = secnorm.Pipeline.from_preset("nlp_preprocessing")
    raw = "First paragraph.\n\n\n\nSecond paragraph with coooool words."
    result = pipeline.run(raw)

    # In structural whitespace mode, max 2 newlines preserved
    assert "\n\n" in result.normalized_text
    assert "\n\n\n" not in result.normalized_text
    assert "cool" in result.normalized_text
    assert result.language.primary_language == "en"


def test_phase2_idempotency():
    cases = [
        "  Ａｄｍｉｎ &amp; 배​포  coooooool ㅋㅋㅋㅋㅋ  ",
        "Hellooooooo world!!!!! https://example.com/path",
        "これはテストですすすすすす",
    ]
    for text in cases:
        once = secnorm.normalize(text).normalized_text
        twice = secnorm.normalize(once).normalized_text
        assert once == twice
