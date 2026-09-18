"""Deterministic, rule-based risk scoring and signal aggregation engine (`docs/02-architecture.md`, `docs/13-roadmap.md`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .models import NormalizationResult, SuspicionFlag

RiskLevel = Literal["safe", "low", "medium", "high", "critical"]
ActionRecommendation = Literal["allow", "flag", "block"]

_DEFAULT_SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 0.8,
    "high": 0.5,
    "medium": 0.25,
    "low": 0.1,
}

_DEFAULT_CATEGORY_MULTIPLIERS: dict[str, float] = {
    "prompt_injection": 1.5,
    "bidi_override": 1.3,
    "tag_char_smuggling": 1.3,
    "pii_detected": 1.2,
    "encoded_payload": 1.2,
    "decoded_markup": 1.2,
    "homoglyph": 1.1,
    "zero_width_injection": 1.1,
}


@dataclass(slots=True, frozen=True)
class RiskReport:
    """Consolidated risk assessment report derived from suspicion flags."""

    score: float
    level: RiskLevel
    recommended_action: ActionRecommendation
    primary_risks: list[str]
    flags_count: dict[str, int]
    total_flags: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "recommended_action": self.recommended_action,
            "primary_risks": list(self.primary_risks),
            "flags_count": dict(self.flags_count),
            "total_flags": self.total_flags,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RiskReport":
        return cls(
            score=float(d["score"]),
            level=d["level"],
            recommended_action=d["recommended_action"],
            primary_risks=list(d.get("primary_risks", [])),
            flags_count=dict(d.get("flags_count", {})),
            total_flags=int(d.get("total_flags", 0)),
        )


class RiskScorer:
    """Configurable rule-based scorer that evaluates flags into an audit risk score (0.0 - 1.0)."""

    def __init__(
        self,
        severity_weights: dict[str, float] | None = None,
        category_multipliers: dict[str, float] | None = None,
        threshold_block: float = 0.75,
        threshold_flag: float = 0.35,
        synergy_factor: float = 0.1,
    ) -> None:
        self.severity_weights = severity_weights or dict(_DEFAULT_SEVERITY_WEIGHTS)
        self.category_multipliers = category_multipliers or dict(_DEFAULT_CATEGORY_MULTIPLIERS)
        self.threshold_block = threshold_block
        self.threshold_flag = threshold_flag
        self.synergy_factor = synergy_factor

    def evaluate_flags(self, flags: list[SuspicionFlag]) -> RiskReport:
        """Evaluate a list of SuspicionFlags and return a RiskReport."""
        if not flags:
            return RiskReport(
                score=0.0,
                level="safe",
                recommended_action="allow",
                primary_risks=[],
                flags_count={"critical": 0, "high": 0, "medium": 0, "low": 0},
                total_flags=0,
            )

        flags_count: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        categories_seen: set[str] = set()
        raw_score = 0.0

        for f in flags:
            sev = f.severity.lower()
            flags_count[sev] = flags_count.get(sev, 0) + 1
            categories_seen.add(f.category)

            base_w = self.severity_weights.get(sev, 0.1)
            cat_mult = self.category_multipliers.get(f.category, 1.0)
            raw_score += base_w * cat_mult

        # Synergy bonus for multi-vector attacks (e.g. zero-width + homoglyph + bidi)
        if len(categories_seen) > 1:
            raw_score += (len(categories_seen) - 1) * self.synergy_factor

        final_score = min(1.0, max(0.0, round(raw_score, 3)))

        # Prioritize primary risks: critical first, then high, then other
        critical_cats = [f.category for f in flags if f.severity == "critical"]
        high_cats = [f.category for f in flags if f.severity == "high"]
        other_cats = [f.category for f in flags if f.severity not in ("critical", "high")]
        ordered_unique_cats: list[str] = []
        for cat in critical_cats + high_cats + other_cats:
            if cat not in ordered_unique_cats:
                ordered_unique_cats.append(cat)

        # Determine level and action
        if final_score == 0.0:
            level: RiskLevel = "safe"
            action: ActionRecommendation = "allow"
        elif final_score < self.threshold_flag:
            level = "low"
            action = "allow"
        elif final_score < self.threshold_block:
            level = "medium" if final_score < 0.6 else "high"
            action = "flag"
        else:
            level = "critical" if final_score >= 0.9 else "high"
            action = "block"

        return RiskReport(
            score=final_score,
            level=level,
            recommended_action=action,
            primary_risks=ordered_unique_cats[:5],
            flags_count=flags_count,
            total_flags=len(flags),
        )

    def evaluate(self, result: NormalizationResult) -> RiskReport:
        """Evaluate a NormalizationResult and return a RiskReport."""
        return self.evaluate_flags(result.flags)


# Global default scorer instance
default_risk_scorer = RiskScorer()


def evaluate_risk(result: NormalizationResult, scorer: RiskScorer | None = None) -> RiskReport:
    """Convenience function to compute risk score for a NormalizationResult."""
    return (scorer or default_risk_scorer).evaluate(result)
