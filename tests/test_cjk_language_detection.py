"""Unit tests for CJK refinement and extended script ratio detection (`docs/09-step7-language-structural-metadata.md`)."""

import secnorm
from secnorm import compute_script_ratios


def test_japanese_kokuji_and_shinjitai_detection():
    # Pure kanji texts with Japanese-specific Kokuji or Shinjitai markers
    text_shinjitai = "東京駅前の円売場"
    res = secnorm.normalize(text_shinjitai, preset="security_balanced")
    assert res.language.primary_language == "ja"
    assert res.language.language_confidence >= 0.9

    text_kokuji = "峠の畑"
    res2 = secnorm.normalize(text_kokuji, preset="security_balanced")
    assert res2.language.primary_language == "ja"


def test_simplified_chinese_detection():
    text_simplified = "计算机软件开发与测试报告"
    res = secnorm.normalize(text_simplified, preset="security_balanced")
    assert res.language.primary_language == "zh"
    assert res.language.language_confidence >= 0.9

    text_site = "欢迎访问官方网站"
    res2 = secnorm.normalize(text_site, preset="security_balanced")
    assert res2.language.primary_language == "zh"


def test_traditional_chinese_detection():
    text_traditional = "電腦軟體開發與測試報告"
    res = secnorm.normalize(text_traditional, preset="security_balanced")
    assert res.language.primary_language == "zh"
    assert res.language.language_confidence >= 0.9


def test_extended_script_ratios_cyrillic_greek_arabic():
    # Cyrillic
    ru_text = "Привет мир! Это тестовая строка."
    ratios_ru = compute_script_ratios(ru_text)
    assert "Cyrillic" in ratios_ru
    res_ru = secnorm.normalize(ru_text)
    assert res_ru.language.primary_language == "ru"

    # Greek
    el_text = "Γειά σου κόσμε! Ελληνικό κείμενο."
    ratios_el = compute_script_ratios(el_text)
    assert "Greek" in ratios_el
    res_el = secnorm.normalize(el_text)
    assert res_el.language.primary_language == "el"

    # Arabic
    ar_text = "مرحبا بالعالم! هذا نص تجريبي."
    ratios_ar = compute_script_ratios(ar_text)
    assert "Arabic" in ratios_ar
    res_ar = secnorm.normalize(ar_text)
    assert res_ar.language.primary_language == "ar"
