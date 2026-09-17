"""Prompt injection and jailbreak guardrail plugin step for LLM security."""

from __future__ import annotations

import re
from typing import Pattern

from ..models import Severity, Span, SuspicionFlag, Transformation
from ..pipeline import PipelineContext, StepOutput
from ..spanmap import Edit

DEFAULT_INJECTION_PATTERNS: dict[str, str] = {
    # 1. System instruction override attempts
    "system_override": (
        r"(?i)\b(?:ignore|disregard|bypass|forget|cancel)\s+(?:all\s+)?"
        r"(?:previous|prior|above|existing)\s+(?:instructions|prompts|rules|directives|constraints)\b"
    ),
    "stop_following_rules": (
        r"(?i)\b(?:do\s+not\s+follow|stop\s+following|no\s+longer\s+bound\s+by)\s+"
        r"(?:the\s+)?(?:previous|above|system|original)\s+(?:rules|instructions|constraints)\b"
    ),
    # 2. Jailbreak / DAN mode roleplay attempts
    "jailbreak_roleplay": (
        r"(?i)\b(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+"
        r"(?:dan|developer\s+mode|unrestricted\s+ai|jailbroken|evil\s+bot|an\s+anti-gpt)\b"
    ),
    "enable_developer_mode": (
        r"(?i)\b(?:enable|activate|switch\s+to)\s+"
        r"(?:developer\s+mode|unrestricted\s+mode|dan\s+mode|debug\s+mode|god\s+mode)\b"
    ),
    "always_say_yes": (
        r"(?i)\b(?:always\s+say\s+yes|never\s+refuse|bypass\s+all\s+safety|ignore\s+content\s+policy)\b"
    ),
    # 3. System prompt leak / extraction
    "system_leak": (
        r"(?i)\b(?:reveal|show|print|display|output|repeat|dump)\s+(?:your\s+)?"
        r"(?:system\s+prompt|initial\s+instructions|pre-prompt|core\s+directives|developer\s+prompt)\b"
    ),
    "what_are_instructions": (
        r"(?i)\bwhat\s+(?:are\s+your|were\s+your)\s+(?:exact\s+)?(?:system|initial)\s+(?:instructions|prompts)\b"
    ),
    # 4. Delimiter and template token smuggling
    "template_tag_smuggling": (
        r"(?i)<\s*(?:system|system_prompt|instruction|rules)\s*>|"
        r"<\s*/\s*(?:system|system_prompt|instruction|rules)\s*>|"
        r"\[\s*(?:INST|SYS|SYSTEM|RULES)\s*\]|"
        r"\[\s*/\s*(?:INST|SYS|SYSTEM|RULES)\s*\]|"
        r"<\|im_start\|>|<\|im_end\|>|<\|system\|>|"
        r"-{3,}\s*(?:BEGIN|START|END)\s+(?:SYSTEM|INSTRUCTION|RULES)\s*-{3,}"
    ),
}


class PromptInjectionGuardrailStep:
    """Specialized guardrail step targeting prompt injections, jailbreaks, and system prompt leaks."""

    name = "prompt_injection_guardrail"

    def __init__(
        self,
        *,
        severity: Severity = "critical",
        mask: str | None = None,
        categories: list[str] | None = None,
        custom_patterns: dict[str, str | Pattern[str]] | None = None,
        name: str = "prompt_injection_guardrail",
    ) -> None:
        self.name = name
        self.severity = severity
        self.mask = mask

        raw_patterns: dict[str, str | Pattern[str]] = {}
        for cat, pat in DEFAULT_INJECTION_PATTERNS.items():
            if categories is None or cat in categories:
                raw_patterns[cat] = pat

        if custom_patterns:
            raw_patterns.update(custom_patterns)

        self.patterns: dict[str, Pattern[str]] = {
            k: re.compile(v) if isinstance(v, str) else v
            for k, v in raw_patterns.items()
        }

    def apply(self, ctx: PipelineContext) -> StepOutput:
        text = ctx.text
        flags: list[SuspicionFlag] = []
        transformations: list[Transformation] = []
        edits: list[Edit] = []

        all_matches: list[tuple[int, int, str, str]] = []
        for cat, regex in self.patterns.items():
            for m in regex.finditer(text):
                all_matches.append((m.start(), m.end(), cat, m.group(0)))

        if not all_matches:
            return StepOutput(text=text)

        # Sort matches by start position, then longest match first
        all_matches.sort(key=lambda m: (m[0], -(m[1] - m[0])))
        filtered_matches: list[tuple[int, int, str, str]] = []
        last_end = -1
        for start, end, cat, matched_str in all_matches:
            if start >= last_end:
                filtered_matches.append((start, end, cat, matched_str))
                last_end = end

        new_text = text
        if self.mask is not None:
            for start, end, cat, matched_str in reversed(filtered_matches):
                src_span = Span(start, end)
                dst_span = Span(start, start + len(self.mask))
                raw_span = ctx.span_map.to_raw(src_span)

                flags.append(
                    SuspicionFlag(
                        category="prompt_injection",
                        severity=self.severity,
                        step=self.name,
                        span=raw_span,
                        detail=f"detected {cat}: {matched_str[:40]}",
                        metadata={"subcategory": cat, "matched_pattern": matched_str},
                    )
                )
                transformations.append(
                    Transformation(
                        step=self.name,
                        rule=f"mask_{cat}",
                        original=matched_str,
                        replacement=self.mask,
                        span_before=src_span,
                        span_after=dst_span,
                    )
                )
                edits.append(Edit(src_span=src_span, dst_span=dst_span))
                new_text = new_text[:start] + self.mask + new_text[end:]

            flags.reverse()
            transformations.reverse()
            edits.reverse()
        else:
            for start, end, cat, matched_str in filtered_matches:
                src_span = Span(start, end)
                raw_span = ctx.span_map.to_raw(src_span)
                flags.append(
                    SuspicionFlag(
                        category="prompt_injection",
                        severity=self.severity,
                        step=self.name,
                        span=raw_span,
                        detail=f"detected {cat}: {matched_str[:40]}",
                        metadata={"subcategory": cat, "matched_pattern": matched_str},
                    )
                )

        return StepOutput(
            text=new_text,
            transformations=transformations,
            flags=flags,
            edits=edits,
        )
