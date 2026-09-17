from collections.abc import Sequence

from .config import (
    EncodingEscapingStepConfig,
    InvisibleControlStepConfig,
    LanguageStructuralStepConfig,
    NormalizationConfig,
    ObfuscationStepConfig,
    RepeatedCharStepConfig,
    UnicodeStepConfig,
    WhitespaceStepConfig,
)
from .models import (
    LanguageMetadata,
    NormalizationResult,
    Span,
    StructuralHints,
    SuspicionFlag,
    Transformation,
)
from .pipeline import (
    NormalizationPipeline,
    Pipeline,
    PipelineContext,
    PipelineStep,
    StepOutput,
)
from .presets import build_preset
from .spanmap import Edit, SpanMap
from .steps import (
    EncodingEscapingStep,
    InvisibleControlStep,
    LanguageStructuralStep,
    ObfuscationStep,
    RepeatedCharStep,
    UnicodeStep,
    WhitespaceStep,
    compute_script_ratios,
)


def normalize(
    text: str,
    preset: str = "security_balanced",
    *,
    config: NormalizationConfig | None = None,
) -> NormalizationResult:
    """Normalize text using a preset pipeline (default: 'security_balanced')."""
    pipeline = build_preset(preset)
    if config is not None:
        pipeline.config = config
    return pipeline.run(text)


def normalize_batch(
    texts: Sequence[str],
    preset: str = "security_balanced",
    *,
    config: NormalizationConfig | None = None,
    n_jobs: int = 1,
) -> list[NormalizationResult]:
    """Normalize multiple texts using a preset pipeline."""
    pipeline = build_preset(preset)
    if config is not None:
        pipeline.config = config

    if n_jobs <= 1 or len(texts) <= 1:
        return [pipeline.run(t) for t in texts]

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=n_jobs) as executor:
        return list(executor.map(pipeline.run, texts))


from .streaming import normalize_file, normalize_stream

__all__ = [
    "Edit",
    "EncodingEscapingStep",
    "EncodingEscapingStepConfig",
    "InvisibleControlStep",
    "InvisibleControlStepConfig",
    "LanguageMetadata",
    "LanguageStructuralStep",
    "LanguageStructuralStepConfig",
    "NormalizationConfig",
    "NormalizationPipeline",
    "NormalizationResult",
    "ObfuscationStep",
    "ObfuscationStepConfig",
    "Pipeline",
    "PipelineContext",
    "PipelineStep",
    "RepeatedCharStep",
    "RepeatedCharStepConfig",
    "Span",
    "SpanMap",
    "StepOutput",
    "StructuralHints",
    "SuspicionFlag",
    "Transformation",
    "UnicodeStep",
    "UnicodeStepConfig",
    "WhitespaceStep",
    "WhitespaceStepConfig",
    "build_preset",
    "compute_script_ratios",
    "normalize",
    "normalize_batch",
    "normalize_file",
    "normalize_stream",
]
