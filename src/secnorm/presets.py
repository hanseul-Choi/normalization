"""Preset pipeline construction (docs/10-api-design.md, docs/13-roadmap.md Phase 2).

In Phase 2:
- `minimal` (unicode NFC + whitespace trim)
- `nlp_preprocessing` (steps 1-5 + 7, whitespace structural mode)
- `security_balanced` (steps 1-5 + 7, whitespace strict mode)
are fully supported. `security_strict` and `llm_input_sanitize` require
step 6 (obfuscation) and raise NotImplementedError until Phase 3/4.
"""

from __future__ import annotations

from .config import NormalizationConfig
from .pipeline import NormalizationPipeline, PipelineStep
from .steps import (
    EncodingEscapingStep,
    InvisibleControlStep,
    LanguageStructuralStep,
    RepeatedCharStep,
    UnicodeStep,
    WhitespaceStep,
)

_UNIMPLEMENTED_PRESETS = (
    "security_strict",
    "llm_input_sanitize",
)


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
        steps = [
            UnicodeStep(),
            InvisibleControlStep(),
            WhitespaceStep(),
            EncodingEscapingStep(),
            RepeatedCharStep(),
            LanguageStructuralStep(),
        ]
        return NormalizationPipeline(steps, config, name=name)

    if name in _UNIMPLEMENTED_PRESETS:
        raise NotImplementedError(
            f"preset {name!r} needs steps not implemented until a later phase "
            "(docs/13-roadmap.md Phase 3)"
        )

    raise ValueError(f"unknown preset: {name!r}")
