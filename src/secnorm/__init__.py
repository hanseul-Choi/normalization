from collections.abc import Sequence
from typing import Literal

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
    PIPELINE_VERSION,
    NormalizationPipeline,
    Pipeline,
    PipelineContext,
    PipelineStep,
    StepOutput,
)
from .presets import build_preset
from .spanmap import Edit, SpanMap

__version__ = PIPELINE_VERSION
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


def _batch_worker(item: tuple[str, str, NormalizationConfig | None]) -> NormalizationResult:
    text, preset, cfg = item
    pipeline = build_preset(preset)
    if cfg is not None:
        pipeline.config = cfg
    return pipeline.run(text)


def normalize_batch(
    texts: Sequence[str],
    preset: str = "security_balanced",
    *,
    config: NormalizationConfig | None = None,
    n_jobs: int = 1,
    backend: Literal["thread", "process"] = "thread",
) -> list[NormalizationResult]:
    """Normalize multiple texts using a preset pipeline with thread or process parallelism."""
    if backend not in ("thread", "process"):
        raise ValueError(f"invalid backend: {backend!r}, expected 'thread' or 'process'")

    pipeline = build_preset(preset)
    if config is not None:
        pipeline.config = config

    if n_jobs <= 1 or len(texts) <= 1:
        return [pipeline.run(t) for t in texts]

    if backend == "process":
        from concurrent.futures import ProcessPoolExecutor

        tasks = [(t, preset, config) for t in texts]
        with ProcessPoolExecutor(max_workers=n_jobs) as executor:
            return list(executor.map(_batch_worker, tasks))

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=n_jobs) as executor:
        return list(executor.map(pipeline.run, texts))


from .risk import RiskReport, RiskScorer, evaluate_risk
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
    "PIPELINE_VERSION",
    "Pipeline",
    "PipelineContext",
    "PipelineStep",
    "RepeatedCharStep",
    "RepeatedCharStepConfig",
    "RiskReport",
    "RiskScorer",
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
    "__version__",
    "build_preset",
    "compute_script_ratios",
    "evaluate_risk",
    "normalize",
    "normalize_batch",
    "normalize_file",
    "normalize_stream",
]
