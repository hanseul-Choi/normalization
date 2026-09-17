"""Preset pipeline construction (docs/10-api-design.md, docs/13-roadmap.md Phase 1).

In Phase 1, `minimal` (unicode NFC + whitespace trim) and `security_balanced`
(reduced 4-step version: unicode NFKC + invisible_control + whitespace strict +
encoding_escaping) are fully supported. The other presets need steps 5-7
and raise NotImplementedError until the corresponding phases land.
"""

from __future__ import annotations

from .config import NormalizationConfig
from .pipeline import NormalizationPipeline, PipelineStep
from .steps import (
    EncodingEscapingStep,
    InvisibleControlStep,
    UnicodeStep,
    WhitespaceStep,
)

_UNIMPLEMENTED_PRESETS = (
    "security_strict",
    "llm_input_sanitize",
    "nlp_preprocessing",
)


def build_preset(name: str) -> NormalizationPipeline:
    if name == "minimal":
        config = NormalizationConfig(enabled_steps={"unicode", "whitespace"})
        config.unicode.form = "NFC"
        config.whitespace.trim_edges = True
        steps: list[PipelineStep] = [UnicodeStep(), WhitespaceStep()]
        return NormalizationPipeline(steps, config, name=name)

    if name == "security_balanced":
        config = NormalizationConfig(
            enabled_steps={"unicode", "invisible_control", "whitespace", "encoding_escaping"}
        )
        steps = [
            UnicodeStep(),
            InvisibleControlStep(),
            WhitespaceStep(),
            EncodingEscapingStep(),
        ]
        return NormalizationPipeline(steps, config, name=name)

    if name in _UNIMPLEMENTED_PRESETS:
        raise NotImplementedError(
            f"preset {name!r} needs steps not implemented until a later phase "
            "(docs/13-roadmap.md Phase 2/3)"
        )

    raise ValueError(f"unknown preset: {name!r}")
