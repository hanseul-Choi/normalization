"""Core data model for secnorm (`docs/02-architecture.md`)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .spanmap import SpanMap

Severity = Literal["low", "medium", "high", "critical"]


@dataclass(slots=True, frozen=True)
class Span:
    start: int
    end: int

    def to_dict(self) -> dict[str, int]:
        return {"start": self.start, "end": self.end}

    @classmethod
    def from_dict(cls, d: dict[str, int]) -> "Span":
        return cls(start=d["start"], end=d["end"])


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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Transformation":
        return cls(
            step=d["step"],
            rule=d["rule"],
            original=d["original"],
            replacement=d["replacement"],
            span_before=Span.from_dict(d["span_before"]),
            span_after=Span.from_dict(d["span_after"]),
            metadata=dict(d.get("metadata", {})),
        )


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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SuspicionFlag":
        return cls(
            category=d["category"],
            severity=d["severity"],
            step=d["step"],
            span=Span.from_dict(d["span"]),
            detail=d["detail"],
            metadata=dict(d.get("metadata", {})),
        )


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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StructuralHints":
        return cls(
            has_html=bool(d["has_html"]),
            has_markdown=bool(d["has_markdown"]),
            has_url=bool(d["has_url"]),
            has_email=bool(d["has_email"]),
            has_code_block=bool(d["has_code_block"]),
            sentence_count=int(d["sentence_count"]),
            word_count=int(d["word_count"]),
            direction=d.get("direction", "ltr"),
        )


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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LanguageMetadata":
        return cls(
            primary_language=d.get("primary_language"),
            language_confidence=float(d.get("language_confidence", 0.0)),
            script_ratios=dict(d.get("script_ratios", {})),
            is_mixed_script=bool(d.get("is_mixed_script", False)),
            structural=StructuralHints.from_dict(d["structural"]),
        )


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
            report_dict = self.evaluate_risk().to_dict()
            data["risk_report"] = report_dict
            data["risk"] = report_dict

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

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NormalizationResult":
        from .spanmap import SpanMap

        span_map_data = d.get("span_map")
        if span_map_data is not None and isinstance(span_map_data, dict):
            span_map = SpanMap.from_dict(span_map_data)
        else:
            span_map = SpanMap.identity(len(d.get("normalized_text", "")))

        return cls(
            raw_text=d.get("raw_text") if d.get("raw_text") is not None else d.get("normalized_text", ""),
            normalized_text=d["normalized_text"],
            normalized_variants=dict(d.get("normalized_variants", {})),
            transformations=[Transformation.from_dict(t) for t in d.get("transformations", [])],
            flags=[SuspicionFlag.from_dict(f) for f in d.get("flags", [])],
            language=LanguageMetadata.from_dict(d["language"]),
            span_map=span_map,
            config_name=d.get("config_name", "custom"),
            pipeline_version=d.get("pipeline_version", "unknown"),
            rule_data_version=dict(d.get("rule_data_version", {})),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "NormalizationResult":
        data = json.loads(json_str)
        return cls.from_dict(data)

