"""Core data model for secnorm (`docs/02-architecture.md`)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .spanmap import SpanMap

Severity = Literal["low", "medium", "high"]


@dataclass(slots=True, frozen=True)
class Span:
    start: int
    end: int

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}


@dataclass(slots=True, frozen=True)
class Transformation:
    step: str
    rule: str
    original: str
    replacement: str
    span_before: Span
    span_after: Span
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "rule": self.rule,
            "original": self.original,
            "replacement": self.replacement,
            "span_before": self.span_before.to_dict(),
            "span_after": self.span_after.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True, frozen=True)
class SuspicionFlag:
    category: str
    severity: Severity
    step: str
    span: Span
    detail: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "step": self.step,
            "span": self.span.to_dict(),
            "detail": self.detail,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True, frozen=True)
class StructuralHints:
    has_html: bool
    has_markdown: bool
    has_url: bool
    has_email: bool
    has_code_block: bool
    sentence_count: int
    word_count: int
    direction: Literal["ltr", "rtl", "mixed"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_html": self.has_html,
            "has_markdown": self.has_markdown,
            "has_url": self.has_url,
            "has_email": self.has_email,
            "has_code_block": self.has_code_block,
            "sentence_count": self.sentence_count,
            "word_count": self.word_count,
            "direction": self.direction,
        }


@dataclass(slots=True, frozen=True)
class LanguageMetadata:
    primary_language: str | None
    language_confidence: float
    script_ratios: dict[str, float]
    is_mixed_script: bool
    structural: StructuralHints

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_language": self.primary_language,
            "language_confidence": self.language_confidence,
            "script_ratios": dict(self.script_ratios),
            "is_mixed_script": self.is_mixed_script,
            "structural": self.structural.to_dict(),
        }


@dataclass(slots=True, frozen=True)
class NormalizationResult:
    raw_text: str
    normalized_text: str
    normalized_variants: dict[str, str]
    transformations: list[Transformation]
    flags: list[SuspicionFlag]
    language: LanguageMetadata
    span_map: "SpanMap"
    config_name: str
    pipeline_version: str
    rule_data_version: dict[str, str]

    def evaluate_risk(self, scorer: Any | None = None) -> Any:
        """Calculate and return consolidated RiskReport."""
        from .risk import evaluate_risk

        return evaluate_risk(self, scorer=scorer)

    def to_dict(self, include_raw_text: bool = True, include_risk: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "normalized_text": self.normalized_text,
            "normalized_variants": dict(self.normalized_variants),
            "transformations": [t.to_dict() for t in self.transformations],
            "flags": [f.to_dict() for f in self.flags],
            "language": self.language.to_dict(),
            "span_map": self.span_map.to_dict() if hasattr(self.span_map, "to_dict") else None,
            "config_name": self.config_name,
            "pipeline_version": self.pipeline_version,
            "rule_data_version": dict(self.rule_data_version),
        }
        if include_raw_text:
            data["raw_text"] = self.raw_text
        else:
            data["raw_text"] = None

        if include_risk:
            data["risk_report"] = self.evaluate_risk().to_dict()

        return data

    def to_json(
        self,
        include_raw_text: bool = True,
        include_risk: bool = False,
        *,
        indent: int | None = None,
    ) -> str:
        return json.dumps(
            self.to_dict(include_raw_text=include_raw_text, include_risk=include_risk),
            ensure_ascii=False,
            indent=indent,
        )
