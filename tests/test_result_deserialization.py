"""Unit tests for NormalizationResult and SpanMap roundtrip deserialization and risk report consistency."""

import json
from pathlib import Path
import pytest

import secnorm
from secnorm.models import (
    LanguageMetadata,
    NormalizationResult,
    Span,
    StructuralHints,
    SuspicionFlag,
    Transformation,
)
from secnorm.risk import RiskReport, RiskScorer
from secnorm.spanmap import SpanMap
from secnorm.cli import main as cli_main


def test_span_from_dict():
    s = Span(3, 10)
    d = s.to_dict()
    restored = Span.from_dict(d)
    assert restored.start == 3
    assert restored.end == 10
    assert restored == s


def test_transformation_from_dict():
    t = Transformation(
        step="whitespace",
        rule="collapse_spaces",
        original="   ",
        replacement=" ",
        span_before=Span(2, 5),
        span_after=Span(2, 3),
        metadata={"count": 3},
    )
    d = t.to_dict()
    restored = Transformation.from_dict(d)
    assert restored.step == "whitespace"
    assert restored.rule == "collapse_spaces"
    assert restored.original == "   "
    assert restored.replacement == " "
    assert restored.span_before == Span(2, 5)
    assert restored.span_after == Span(2, 3)
    assert restored.metadata == {"count": 3}
    assert restored == t


def test_suspicion_flag_from_dict():
    f = SuspicionFlag(
        category="homoglyph",
        severity="high",
        step="obfuscation",
        span=Span(5, 10),
        detail="cyrillic 'а' mixed with latin",
        metadata={"target": "apple.com"},
    )
    d = f.to_dict()
    restored = SuspicionFlag.from_dict(d)
    assert restored.category == "homoglyph"
    assert restored.severity == "high"
    assert restored.step == "obfuscation"
    assert restored.span == Span(5, 10)
    assert restored.detail == "cyrillic 'а' mixed with latin"
    assert restored.metadata == {"target": "apple.com"}
    assert restored == f


def test_structural_hints_from_dict():
    hints = StructuralHints(
        has_html=True,
        has_markdown=False,
        has_url=True,
        has_email=False,
        has_code_block=False,
        sentence_count=2,
        word_count=15,
        direction="ltr",
    )
    d = hints.to_dict()
    restored = StructuralHints.from_dict(d)
    assert restored.has_html is True
    assert restored.has_url is True
    assert restored.sentence_count == 2
    assert restored.word_count == 15
    assert restored.direction == "ltr"
    assert restored == hints


def test_language_metadata_from_dict():
    meta = LanguageMetadata(
        primary_language="ko",
        language_confidence=0.98,
        script_ratios={"Hangul": 0.85, "Latin": 0.15},
        is_mixed_script=True,
        structural=StructuralHints(
            has_html=False,
            has_markdown=False,
            has_url=False,
            has_email=False,
            has_code_block=False,
            sentence_count=1,
            word_count=5,
            direction="ltr",
        ),
    )
    d = meta.to_dict()
    restored = LanguageMetadata.from_dict(d)
    assert restored.primary_language == "ko"
    assert restored.language_confidence == 0.98
    assert restored.script_ratios == {"Hangul": 0.85, "Latin": 0.15}
    assert restored.is_mixed_script is True
    assert restored.structural.direction == "ltr"
    assert restored == meta


def test_normalization_result_roundtrip_dict():
    raw = "  안녕하세요! Check https://аpple.com/login &amp; user@example.com  "
    result = secnorm.normalize(raw, preset="security_balanced")

    d = result.to_dict(include_raw_text=True)
    restored = NormalizationResult.from_dict(d)

    assert restored.raw_text == result.raw_text
    assert restored.normalized_text == result.normalized_text
    assert restored.normalized_variants == result.normalized_variants
    assert len(restored.transformations) == len(result.transformations)
    assert len(restored.flags) == len(result.flags)
    assert restored.language.primary_language == result.language.primary_language
    assert restored.config_name == result.config_name
    assert restored.pipeline_version == result.pipeline_version

    # Verify SpanMap tracking on restored result
    # Original homoglyph "apple"
    start_pos = restored.normalized_text.find("apple.com")
    assert start_pos != -1
    raw_span = restored.span_map.to_raw(Span(start_pos, start_pos + 9))
    assert "аpple.com" in raw[raw_span.start : raw_span.end]


def test_normalization_result_roundtrip_json():
    raw = "100% discount! Contact support@example.com or visit http://phish.example.com"
    result = secnorm.normalize(raw, preset="security_strict")

    json_str = result.to_json(include_raw_text=True)
    restored = NormalizationResult.from_json(json_str)

    assert restored.raw_text == raw
    assert restored.normalized_text == result.normalized_text
    assert len(restored.transformations) == len(result.transformations)


def test_risk_scorer_empty_flags_count_critical():
    scorer = RiskScorer()
    report = scorer.evaluate_flags([])

    assert report.score == 0.0
    assert report.level == "safe"
    assert report.recommended_action == "allow"
    # Ensure 'critical' key is always present in flags_count dictionary
    assert "critical" in report.flags_count
    assert report.flags_count["critical"] == 0
    assert report.flags_count["high"] == 0
    assert report.flags_count["medium"] == 0
    assert report.flags_count["low"] == 0


def test_risk_report_from_dict():
    original = RiskReport(
        score=0.92,
        level="critical",
        recommended_action="block",
        primary_risks=["prompt_injection", "homoglyph"],
        flags_count={"critical": 1, "high": 1, "medium": 0, "low": 0},
        total_flags=2,
    )
    d = original.to_dict()
    restored = RiskReport.from_dict(d)

    assert restored.score == 0.92
    assert restored.level == "critical"
    assert restored.recommended_action == "block"
    assert restored.primary_risks == ["prompt_injection", "homoglyph"]
    assert restored.flags_count == {"critical": 1, "high": 1, "medium": 0, "low": 0}
    assert restored.total_flags == 2
    assert restored == original


def test_cli_and_streaming_file_score_flag(tmp_path: Path):
    """Verify --score flag correctly embeds risk data in batch file processing and jsonl."""
    input_file = tmp_path / "in.txt"
    output_file = tmp_path / "out.jsonl"

    input_file.write_text("Hello world\nCheck https://аpple.com\n", encoding="utf-8")

    # 1. Test single worker file conversion with --score
    ret = cli_main([
        "-i", str(input_file),
        "-o", str(output_file),
        "-p", "security_balanced",
        "-s",
        "--format", "jsonl",
    ])
    assert ret == 0
    lines = [json.loads(line) for line in output_file.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    # Verify risk report is included in both lines
    assert "risk_report" in lines[0] or "risk" in lines[0]
    assert "risk_report" in lines[1] or "risk" in lines[1]
    assert lines[1]["risk_report"]["score"] > 0.0

    # 2. Test multi-process parallel batch conversion with --score
    output_parallel = tmp_path / "out_parallel.jsonl"
    ret_parallel = cli_main([
        "-i", str(input_file),
        "-o", str(output_parallel),
        "-p", "security_balanced",
        "-s",
        "-j", "2",
        "--backend", "process",
        "--format", "jsonl",
    ])
    assert ret_parallel == 0
    lines_p = [json.loads(line) for line in output_parallel.read_text(encoding="utf-8").splitlines()]
    assert len(lines_p) == 2
    assert "risk_report" in lines_p[1] or "risk" in lines_p[1]
    assert lines_p[1]["risk_report"]["score"] > 0.0
