"""Personally Identifiable Information (PII) detection and redaction guardrail plugin step."""

from __future__ import annotations

import re
from typing import Any, Pattern

from ..models import Severity, Span, SuspicionFlag, Transformation
from ..pipeline import PipelineContext, StepOutput
from ..spanmap import Edit

# Luhn algorithm for credit card numbers
def validate_luhn(number_str: str) -> bool:
    digits = [int(c) for c in number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            d = d * 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# Korean Resident Registration Number (RRN) validation
def validate_korean_rrn(rrn_str: str) -> bool:
    digits = [int(c) for c in rrn_str if c.isdigit()]
    if len(digits) != 13:
        return False
    # Valid gender codes: 1-4 (traditional), 5-8 (foreigners)
    if digits[6] not in range(1, 9):
        return False

    weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
    s = sum(w * d for w, d in zip(weights, digits[:12]))
    remainder = (11 - (s % 11)) % 10
    # True if checksum matches or 2020-Oct post-reform random assignment
    return remainder == digits[12]


# Patterns
_CARD_RE = re.compile(r"\b(?:\d{4}[- ]?){3}\d{1,7}\b")
_RRN_RE = re.compile(r"\b\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[- ]?[1-8]\d{6}\b")
_PHONE_RE = re.compile(
    r"(?:\+?82[- ]?|0)(?:1[016789]|2|[3-6][1-5])[- ]?\d{3,4}[- ]?\d{4}\b|"
    r"\+\d{1,3}[- ]?\d{2,4}[- ]?\d{3,4}[- ]?\d{4}\b"
)
_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
_IPV4_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\b"
)

DEFAULT_PII_MASKS: dict[str, str] = {
    "credit_card": "[CREDIT_CARD]",
    "rrn": "[RESIDENT_NUMBER]",
    "phone": "[PHONE_NUMBER]",
    "email": "[EMAIL]",
    "ip": "[IP_ADDRESS]",
}


class PIIGuardrailStep:
    """Detects, audits, and optionally masks Personally Identifiable Information (PII)."""

    name = "pii_guardrail"

    def __init__(
        self,
        *,
        mask: bool | str | dict[str, str] = True,
        types: list[str] | None = None,
        severity: Severity = "high",
        validate_checksums: bool = True,
        name: str = "pii_guardrail",
    ) -> None:
        self.name = name
        self.mask_option = mask
        self.severity = severity
        self.validate_checksums = validate_checksums

        valid_types = {"credit_card", "rrn", "phone", "email", "ip"}
        if types is not None:
            self.types = set(types)
        else:
            self.types = valid_types

    def _get_mask(self, pii_type: str) -> str | None:
        if self.mask_option is False:
            return None
        if isinstance(self.mask_option, str):
            return self.mask_option
        if isinstance(self.mask_option, dict):
            return self.mask_option.get(pii_type, DEFAULT_PII_MASKS.get(pii_type, "[PII]"))
        return DEFAULT_PII_MASKS.get(pii_type, "[PII]")

    def apply(self, ctx: PipelineContext) -> StepOutput:
        text = ctx.text
        flags: list[SuspicionFlag] = []
        transformations: list[Transformation] = []
        edits: list[Edit] = []

        all_matches: list[tuple[int, int, str, str]] = []  # start, end, type, matched_str

        # 1. Credit Card
        if "credit_card" in self.types:
            for m in _CARD_RE.finditer(text):
                matched = m.group(0)
                if not self.validate_checksums or validate_luhn(matched):
                    all_matches.append((m.start(), m.end(), "credit_card", matched))

        # 2. Korean RRN
        if "rrn" in self.types:
            for m in _RRN_RE.finditer(text):
                matched = m.group(0)
                if not self.validate_checksums or validate_korean_rrn(matched):
                    all_matches.append((m.start(), m.end(), "rrn", matched))

        # 3. Phone
        if "phone" in self.types:
            for m in _PHONE_RE.finditer(text):
                matched = m.group(0)
                all_matches.append((m.start(), m.end(), "phone", matched))

        # 4. Email
        if "email" in self.types:
            for m in _EMAIL_RE.finditer(text):
                matched = m.group(0)
                all_matches.append((m.start(), m.end(), "email", matched))

        # 5. IP Address
        if "ip" in self.types:
            for m in _IPV4_RE.finditer(text):
                matched = m.group(0)
                all_matches.append((m.start(), m.end(), "ip", matched))

        if not all_matches:
            return StepOutput(text=text)

        # Eliminate overlaps (priority: longest match, earlier start)
        all_matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        filtered_matches: list[tuple[int, int, str, str]] = []
        last_end = -1
        for start, end, p_type, matched_str in all_matches:
            if start >= last_end:
                filtered_matches.append((start, end, p_type, matched_str))
                last_end = end

        new_text = text
        if self.mask_option is not False:
            for start, end, p_type, matched_str in reversed(filtered_matches):
                mask_str = self._get_mask(p_type) or "[PII]"
                src_span = Span(start, end)
                dst_span = Span(start, start + len(mask_str))
                raw_span = ctx.span_map.to_raw(src_span)

                flags.append(
                    SuspicionFlag(
                        category="pii_detected",
                        severity=self.severity,
                        step=self.name,
                        span=raw_span,
                        detail=f"detected PII ({p_type}): {mask_str}",
                        metadata={"pii_type": p_type, "masked_replacement": mask_str},
                    )
                )
                transformations.append(
                    Transformation(
                        step=self.name,
                        rule=f"mask_{p_type}",
                        original=matched_str,
                        replacement=mask_str,
                        span_before=src_span,
                        span_after=dst_span,
                    )
                )
                edits.append(Edit(src_span=src_span, dst_span=dst_span))
                new_text = new_text[:start] + mask_str + new_text[end:]

            flags.reverse()
            transformations.reverse()
            edits.reverse()
        else:
            for start, end, p_type, matched_str in filtered_matches:
                src_span = Span(start, end)
                raw_span = ctx.span_map.to_raw(src_span)
                flags.append(
                    SuspicionFlag(
                        category="pii_detected",
                        severity=self.severity,
                        step=self.name,
                        span=raw_span,
                        detail=f"detected PII ({p_type})",
                        metadata={"pii_type": p_type},
                    )
                )

        return StepOutput(
            text=new_text,
            transformations=transformations,
            flags=flags,
            edits=edits,
        )
