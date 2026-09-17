import pytest

import secnorm


def test_adversarial_homoglyph_domain_spoofing():
    # Cyrillic 'а' (U+0430) spoofing apple.com
    spoofed = "https://\u0430pple.com/login"
    result = secnorm.normalize(spoofed, preset="security_balanced")

    # Canonical should fold homoglyph to ASCII 'a'
    assert "https://apple.com/login" == result.normalized_text
    categories = [f.category for f in result.flags]
    assert "homoglyph" in categories
    flag = next(f for f in result.flags if f.category == "homoglyph")
    assert flag.severity == "high"


def test_adversarial_trojan_source_bidi_override():
    # RLO (U+202E) reversing characters visually
    raw = "access_level = 'user\u202e \u2066// Check if admin\u2069 \u2066'; // admin"
    result = secnorm.normalize(raw, preset="security_balanced")

    # Bidi characters should be stripped
    assert "\u202e" not in result.normalized_text
    assert "\u2066" not in result.normalized_text
    assert "\u2069" not in result.normalized_text
    assert any(f.category == "bidi_override" for f in result.flags)


def test_adversarial_tag_character_ascii_smuggling():
    # Prompt injection using Unicode Tag characters (U+E0000 block)
    hidden_instruction = "".join(chr(0xE0000 + ord(c)) for c in "DROP TABLE")
    raw = f"Normal user query {hidden_instruction}"
    result = secnorm.normalize(raw, preset="security_balanced")

    # Tag characters must be completely removed
    assert result.normalized_text == "Normal user query"
    assert any(f.category == "tag_char_smuggling" for f in result.flags)
    flag = next(f for f in result.flags if f.category == "tag_char_smuggling")
    assert flag.severity == "high"


def test_adversarial_zero_width_steganography():
    # Zero width spaces inserted inside forbidden words
    raw = "무료 배\u200b포 이\u200c벤\u200d트"
    result = secnorm.normalize(raw, preset="security_balanced")

    assert result.normalized_text == "무료 배포 이벤트"
    assert any(f.category == "zero_width_injection" for f in result.flags)


def test_adversarial_leetspeak_and_delimiter_spam():
    # Leetspeak combined with spaces/delimiters
    raw = "f.r.e.e  m.o.n.e.y  n0w  g3t  1t"
    result = secnorm.normalize(raw, preset="security_balanced")

    # Aggressive variant should expose de-obfuscated text
    assert "aggressive" in result.normalized_variants
    aggressive = result.normalized_variants["aggressive"]
    assert "free" in aggressive
    assert "money" in aggressive
    assert "now" in aggressive or "get" in aggressive

    categories = [f.category for f in result.flags]
    assert "separator_injection" in categories or "leetspeak" in categories


def test_adversarial_excessive_repetition_spam():
    raw = "코인 대박!!!!!!!!!!!!!!!!!! ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ"
    result = secnorm.normalize(raw, preset="security_balanced")

    assert "대박!!!" in result.normalized_text
    assert any(f.category == "excessive_repetition" for f in result.flags)
