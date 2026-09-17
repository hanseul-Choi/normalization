"""Core data model for secnorm (`docs/02-architecture.md`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from .spanmap import SpanMap

Severity = Literal["low", "medium", "high"]


@dataclass(slots=True, frozen=True)
class Span:
    start: int
    end: int


@dataclass(slots=True, frozen=True)
class Transformation:
    step: str
    rule: str
    original: str
    replacement: str
    span_before: Span
    span_after: Span
    metadata: dict = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class SuspicionFlag:
    category: str
    severity: Severity
    step: str
    span: Span
    detail: str
    metadata: dict = field(default_factory=dict)


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


@dataclass(slots=True, frozen=True)
class LanguageMetadata:
    primary_language: str | None
    language_confidence: float
    script_ratios: dict[str, float]
    is_mixed_script: bool
    structural: StructuralHints


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
