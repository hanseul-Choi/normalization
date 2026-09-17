"""Preset pipeline construction (docs/10-api-design.md, docs/13-roadmap.md Phase 1).

Only `minimal` (unicode NFC + whitespace trim, per docs/10-api-design.md's
preset table) is fully buildable in Phase 1: the other four presets need
steps 5-7, which don't exist yet. `NormalizationPipeline.from_preset` raises
`NotImplementedError` for those until the corresponding phases land.
"""

from __future__ import annotations

from .config import NormalizationConfig
from .pipeline import NormalizationPipeline, PipelineStep
from .steps import UnicodeStep, WhitespaceStep

_UNIMPLEMENTED_PRESETS = (
    "security_strict",
    "security_balanced",
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

    if name in _UNIMPLEMENTED_PRESETS:
        raise NotImplementedError(
            f"preset {name!r} needs steps not implemented until a later phase "
            "(docs/13-roadmap.md Phase 2/3)"
        )

    raise ValueError(f"unknown preset: {name!r}")
