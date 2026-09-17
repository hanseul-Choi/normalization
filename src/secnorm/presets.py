"""Preset pipeline construction (docs/10-api-design.md, docs/13-roadmap.md Phase 3).

All 5 presets are fully implemented:
- `security_strict`: all 7 steps on, decode_and_recurse on, collapse separators in canonical.
- `security_balanced`: default, all 7 steps on, homoglyph canonical, aggressive variants for leet/separators.
- `llm_input_sanitize`: 2nd step fortified (all variation selectors stripped), homoglyph canonical on.
- `nlp_preprocessing`: steps 1-5 + 7 on (obfuscation off), structural whitespace.
- `minimal`: unicode NFC + whitespace trim.
"""

from __future__ import annotations

from .config import NormalizationConfig
from .pipeline import NormalizationPipeline, PipelineStep
from .steps import (
    EncodingEscapingStep,
    InvisibleControlStep,
    LanguageStructuralStep,
    ObfuscationStep,
    RepeatedCharStep,
    UnicodeStep,
    WhitespaceStep,
)

_UNIMPLEMENTED_PRESETS: tuple[str, ...] = ()


def _build_full_steps() -> list[PipelineStep]:
    return [
        UnicodeStep(),
        InvisibleControlStep(),
        WhitespaceStep(),
        EncodingEscapingStep(),
        RepeatedCharStep(),
        ObfuscationStep(),
        LanguageStructuralStep(),
    ]


def build_preset(name: str) -> NormalizationPipeline:
    if name == "minimal":
        config = NormalizationConfig(enabled_steps={"unicode", "whitespace"})
        config.unicode.form = "NFC"
        config.whitespace.trim_edges = True
        steps: list[PipelineStep] = [UnicodeStep(), WhitespaceStep()]
        return NormalizationPipeline(steps, config, name=name)

    if name == "nlp_preprocessing":
        config = NormalizationConfig(
            enabled_steps={
                "unicode",
                "invisible_control",
                "whitespace",
                "encoding_escaping",
                "repeated_char",
                "language_structural",
            }
        )
        config.whitespace.mode = "structural"
        steps = [
            UnicodeStep(),
            InvisibleControlStep(),
            WhitespaceStep(),
            EncodingEscapingStep(),
            RepeatedCharStep(),
            LanguageStructuralStep(),
        ]
        return NormalizationPipeline(steps, config, name=name)

    if name == "security_balanced":
        config = NormalizationConfig()  # all 7 steps enabled by default
        return NormalizationPipeline(_build_full_steps(), config, name=name)

    if name == "security_strict":
        config = NormalizationConfig()
        config.obfuscation.separator_injection_collapse_in_canonical = True
        config.obfuscation.decode_and_recurse = True
        config.encoding_escaping.decode_url_encoding = "always"
        return NormalizationPipeline(_build_full_steps(), config, name=name)

    if name == "llm_input_sanitize":
        config = NormalizationConfig()
        config.invisible_control.strip_variation_selectors = "all"
        config.obfuscation.decode_and_recurse = False
        return NormalizationPipeline(_build_full_steps(), config, name=name)

    raise ValueError(f"unknown preset: {name!r}")
