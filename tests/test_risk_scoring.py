"""Unit and integration tests for RiskScorer and risk evaluation engine (`src/secnorm/risk.py`)."""

import json
import pytest
import secnorm
from secnorm.cli import main
from secnorm.models import SuspicionFlag, Span
from secnorm.risk import RiskScorer, evaluate_risk


def test_risk_scorer_clean_text():
    result = secnorm.normalize("Clean standard English sentence.")
    report = result.evaluate_risk()
    assert report.score == 0.0
    assert report.level == "safe"
    assert report.recommended_action == "allow"
    assert report.total_flags == 0
    assert report.primary_risks == []


def test_risk_scorer_single_homoglyph():
    result = secnorm.normalize("аpple.com", preset="security_balanced")
    report = evaluate_risk(result)
    assert report.score > 0.0
    assert report.total_flags >= 1
    assert "homoglyph" in report.primary_risks
    assert report.flags_count["high"] >= 1


def test_risk_scorer_multi_vector_attack():
    # Text with zero-width, bidi override, and homoglyphs
    attack_text = "\u202e\u200bаpple.com\u202c"
    result = secnorm.normalize(attack_text, preset="security_strict")
    report = result.evaluate_risk()

    assert report.score >= 0.8
    assert report.level in ("high", "critical")
    assert report.recommended_action == "block"
    assert len(report.primary_risks) >= 2


def test_custom_risk_scorer_thresholds():
    strict_scorer = RiskScorer(threshold_block=0.2, threshold_flag=0.1)
    result = secnorm.normalize("coooooool!!!!", preset="security_balanced")
    report = strict_scorer.evaluate(result)

    # Excessive repetition has low severity, but strict scorer blocks at 0.2
    assert report.score > 0.0
    assert report.recommended_action in ("flag", "block")


def test_normalization_result_to_dict_include_risk():
    result = secnorm.normalize("аpple.com")
    d = result.to_dict(include_risk=True)
    assert "risk_report" in d
    assert isinstance(d["risk_report"], dict)
    assert d["risk_report"]["score"] > 0.0
    assert "recommended_action" in d["risk_report"]


def test_cli_score_option(capsys):
    ret = main(["аpple.com", "--score"])
    assert ret == 0
    out, err = capsys.readouterr()
    assert "[Risk: score=" in out
    assert "apple.com" in out


def test_cli_score_with_json(capsys):
    ret = main(["аpple.com", "--json", "--score"])
    assert ret == 0
    out, err = capsys.readouterr()
    data = json.loads(out)
    assert "risk_report" in data
    assert data["risk_report"]["score"] > 0.0
