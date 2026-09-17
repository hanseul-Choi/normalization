"""Tests for multilingual expansion, RTL detection, and European Latin language support (Phase 11)."""

from __future__ import annotations

import pytest

import secnorm
from secnorm.config import LanguageStructuralStepConfig, NormalizationConfig


def test_arabic_rtl_and_language_detection() -> None:
    """Test Arabic text identification and RTL directionality."""
    arabic_text = "مرحبا بكم في عالم البرمجة الآمنة"
    result = secnorm.normalize(arabic_text, preset="security_balanced")

    assert result.language.primary_language == "ar"
    assert result.language.language_confidence >= 0.85
    assert result.language.structural.direction == "rtl"
    assert "Arabic" in result.language.script_ratios
    assert result.language.script_ratios["Arabic"] >= 0.70


def test_hebrew_rtl_and_language_detection() -> None:
    """Test Hebrew text identification and RTL directionality."""
    hebrew_text = "שלום עולם, ברוכים הבאים למערכת"
    result = secnorm.normalize(hebrew_text, preset="security_balanced")

    assert result.language.primary_language == "he"
    assert result.language.language_confidence >= 0.85
    assert result.language.structural.direction == "rtl"
    assert "Hebrew" in result.language.script_ratios
    assert result.language.script_ratios["Hebrew"] >= 0.70


def test_ltr_defaults_for_standard_scripts() -> None:
    """Ensure standard scripts remain LTR."""
    for text, lang in [
        ("Hello, this is a clean English sentence.", "en"),
        ("안녕하세요, 보안 텍스트 정규화입니다.", "ko"),
        ("こんにちは、セキュリティ正規化です。", "ja"),
    ]:
        res = secnorm.normalize(text, preset="security_balanced")
        assert res.language.structural.direction == "ltr"
        assert res.language.primary_language == lang


def test_spanish_unique_markers_detection() -> None:
    """Test Spanish detection via ¡, ¿, and ñ markers."""
    spanish_text = "¡Hola señor! ¿Cómo está usted el día de hoy?"
    result = secnorm.normalize(spanish_text, preset="security_balanced")

    assert result.language.primary_language == "es"
    assert result.language.language_confidence >= 0.90
    assert result.language.structural.direction == "ltr"


def test_german_unique_markers_detection() -> None:
    """Test German detection via ß and umlauts."""
    german_text = "Große Straße und schönes Wetter in München"
    result = secnorm.normalize(german_text, preset="security_balanced")

    assert result.language.primary_language == "de"
    assert result.language.language_confidence >= 0.90
    assert result.language.structural.direction == "ltr"


def test_french_unique_markers_detection() -> None:
    """Test French detection via œ ligature and ç."""
    french_text = "Un grand chef-d'œuvre français avec ça et là"
    result = secnorm.normalize(french_text, preset="security_balanced")

    assert result.language.primary_language == "fr"
    assert result.language.language_confidence >= 0.90
    assert result.language.structural.direction == "ltr"


def test_detect_latin_dialects_disabled() -> None:
    """When detect_latin_dialects is disabled, Latin text defaults to English."""
    cfg = NormalizationConfig(
        language_structural=LanguageStructuralStepConfig(detect_latin_dialects=False)
    )
    result = secnorm.normalize("¡Hola señor!", config=cfg)
    assert result.language.primary_language == "en"


def test_supported_languages_filtering() -> None:
    """When supported_languages is restricted, non-supported languages return None."""
    # Restrict to only Korean and English
    cfg = NormalizationConfig(
        language_structural=LanguageStructuralStepConfig(
            supported_languages=("ko", "en")
        )
    )
    res_es = secnorm.normalize("¡Hola señor!", config=cfg)
    assert res_es.language.primary_language is None
    assert res_es.language.language_confidence == 0.0

    res_ar = secnorm.normalize("مرحبا بكم", config=cfg)
    assert res_ar.language.primary_language is None
    # However structural direction is still computed correctly
    assert res_ar.language.structural.direction == "rtl"

    # When Spanish is included, it is detected
    cfg_with_es = NormalizationConfig(
        language_structural=LanguageStructuralStepConfig(
            supported_languages=("ko", "en", "es")
        )
    )
    res_es2 = secnorm.normalize("¡Hola señor!", config=cfg_with_es)
    assert res_es2.language.primary_language == "es"


def test_config_serialization_with_multilingual_fields() -> None:
    """Verify from_dict and serialization of new multilingual configuration options."""
    data = {
        "language_structural": {
            "detect_latin_dialects": False,
            "supported_languages": ["ko", "en", "ja"],
            "mixed_script_threshold": 0.20,
        }
    }
    cfg = NormalizationConfig.from_dict(data)
    assert cfg.language_structural.detect_latin_dialects is False
    assert cfg.language_structural.supported_languages == ("ko", "en", "ja")
    assert cfg.language_structural.mixed_script_threshold == 0.20
