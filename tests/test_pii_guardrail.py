"""Tests for Personally Identifiable Information (PII) detection and redaction guardrail."""

from __future__ import annotations

import pytest

import secnorm
from secnorm import NormalizationPipeline, Span
from secnorm.plugins import (
    PIIGuardrailStep,
    validate_korean_rrn,
    validate_luhn,
)


def test_validate_luhn_algorithm() -> None:
    """Test Luhn checksum validation for credit card numbers."""
    # Standard valid test card numbers (16 digits)
    assert validate_luhn("4532015012345671") is True
    assert validate_luhn("4532-0150-1234-5671") is True

    # Invalid cards
    assert validate_luhn("1111-2222-3333-4440") is False
    assert validate_luhn("12345") is False  # Too short


def test_credit_card_detection_and_masking() -> None:
    """Test detection and masking of valid credit card numbers."""
    step = PIIGuardrailStep()
    pipeline = NormalizationPipeline(steps=[step])

    text = "Payment details: card 4532-0150-1234-5671 used for transaction."
    res = pipeline.run(text)

    assert "[CREDIT_CARD]" in res.normalized_text
    assert "4532-0150-1234-5671" not in res.normalized_text
    assert len(res.flags) == 1
    assert res.flags[0].category == "pii_detected"
    assert res.flags[0].metadata.get("pii_type") == "credit_card"

    # Span tracking check
    card_idx = res.normalized_text.find("[CREDIT_CARD]")
    raw_span = res.span_map.to_raw(Span(card_idx, card_idx + len("[CREDIT_CARD]")))
    assert text[raw_span.start : raw_span.end] == "4532-0150-1234-5671"


def test_invalid_card_skipped_by_checksum() -> None:
    """Ensure random 16 digit strings that fail Luhn are not flagged as credit cards."""
    step = PIIGuardrailStep(validate_checksums=True)
    pipeline = NormalizationPipeline(steps=[step])

    text = "Order ID 1111-2222-3333-4440 should not be detected as credit card."
    res = pipeline.run(text)

    assert len(res.flags) == 0
    assert res.normalized_text == text


def test_email_and_phone_masking() -> None:
    """Test phone numbers and email detection and redaction."""
    step = PIIGuardrailStep()
    pipeline = NormalizationPipeline(steps=[step])

    text = "Please reach admin@example.com or call 010-9876-5432 for assistance."
    res = pipeline.run(text)

    assert "[EMAIL]" in res.normalized_text
    assert "[PHONE_NUMBER]" in res.normalized_text
    assert "admin@example.com" not in res.normalized_text
    assert "010-9876-5432" not in res.normalized_text
    assert len(res.flags) == 2


def test_ipv4_detection() -> None:
    """Test IPv4 address masking."""
    step = PIIGuardrailStep()
    pipeline = NormalizationPipeline(steps=[step])

    text = "Server connected from 192.168.0.10 securely."
    res = pipeline.run(text)

    assert "[IP_ADDRESS]" in res.normalized_text
    assert "192.168.0.10" not in res.normalized_text
    assert len(res.flags) == 1
    assert res.flags[0].metadata.get("pii_type") == "ip"


def test_custom_single_mask_option() -> None:
    """Test uniform mask string for all PII types."""
    step = PIIGuardrailStep(mask="[REDACTED]")
    pipeline = NormalizationPipeline(steps=[step])

    text = "Contact user@secnorm.org at 010-1111-2222."
    res = pipeline.run(text)

    assert res.normalized_text == "Contact [REDACTED] at [REDACTED]."


def test_audit_only_no_masking() -> None:
    """Test audit-only mode where mask=False generates flags but preserves raw text."""
    step = PIIGuardrailStep(mask=False)
    pipeline = NormalizationPipeline(steps=[step])

    text = "Contact user@secnorm.org."
    res = pipeline.run(text)

    assert res.normalized_text == text
    assert len(res.transformations) == 0
    assert len(res.flags) == 1
    assert res.flags[0].category == "pii_detected"


def test_pii_type_filtering() -> None:
    """Test restricting detection to specific PII types."""
    step = PIIGuardrailStep(types=["email"])
    pipeline = NormalizationPipeline(steps=[step])

    text = "Email: user@example.com, Phone: 010-1234-5678."
    res = pipeline.run(text)

    assert "[EMAIL]" in res.normalized_text
    assert "010-1234-5678" in res.normalized_text
    assert len(res.flags) == 1
    assert res.flags[0].metadata.get("pii_type") == "email"


def test_risk_scoring_with_pii() -> None:
    """Test that detected PII contributes to overall risk evaluation."""
    step = PIIGuardrailStep(mask=True)
    pipeline = NormalizationPipeline(steps=[step])

    text = "Multiple leaks: user@a.com, phone 010-1234-5678, IP 10.0.0.1."
    res = pipeline.run(text)
    report = res.evaluate_risk()

    assert report.total_flags == 3
    assert "pii_detected" in report.primary_risks
    assert report.score > 0.35
    assert report.level in ("medium", "high", "critical")
