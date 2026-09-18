"""Pipeline execution model (`docs/02-architecture.md`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .config import NormalizationConfig
from .data import CONFUSABLES_VERSION
from .diffutil import diff_edits
from .models import (
    LanguageMetadata,
    NormalizationResult,
    StructuralHints,
    SuspicionFlag,
    Transformation,
)
from .spanmap import Edit, SpanMap

PIPELINE_VERSION = "1.0.0"

_EMPTY_LANGUAGE_METADATA = LanguageMetadata(
    primary_language=None,
    language_confidence=0.0,
    script_ratios={},
    is_mixed_script=False,
    structural=StructuralHints(
        has_html=False,
        has_markdown=False,
        has_url=False,
        has_email=False,
        has_code_block=False,
        sentence_count=0,
        word_count=0,
        direction="ltr",
    ),
)


@dataclass
class PipelineContext:
    raw_text: str
    text: str
    config: NormalizationConfig
    span_map: SpanMap
    language: LanguageMetadata | None = None


@dataclass
class StepOutput:
    text: str
    transformations: list[Transformation] = field(default_factory=list)
    flags: list[SuspicionFlag] = field(default_factory=list)
    edits: list[Edit] = field(default_factory=list)
    variants: dict[str, str] = field(default_factory=dict)


class PipelineStep(Protocol):
    name: str

    def apply(self, ctx: PipelineContext) -> StepOutput: ...


class NormalizationPipeline:
    def __init__(
        self,
        steps: list[PipelineStep] | None = None,
        config: NormalizationConfig | None = None,
        name: str = "custom",
    ) -> None:
        self.config = config if config is not None else NormalizationConfig()
        self.name = name
        if steps is not None:
            self._steps = list(steps)
            for s in self._steps:
                self.config.enabled_steps.add(s.name)
        else:
            from .steps import (
                EncodingEscapingStep,
                InvisibleControlStep,
                LanguageStructuralStep,
                ObfuscationStep,
                RepeatedCharStep,
                UnicodeStep,
                WhitespaceStep,
            )

            available = [
                UnicodeStep(),
                InvisibleControlStep(),
                WhitespaceStep(),
                EncodingEscapingStep(),
                RepeatedCharStep(),
                ObfuscationStep(),
                LanguageStructuralStep(),
            ]
            self._steps = [s for s in available if s.name in self.config.enabled_steps]

    def _run_single_pass(self, text: str) -> NormalizationResult:
        span_map = SpanMap.identity(len(text))
        transformations: list[Transformation] = []
        flags: list[SuspicionFlag] = []
        current_text = text
        current_language: LanguageMetadata | None = None
        current_variants: dict[str, str] = {}

        for step in self._steps:
            if step.name not in self.config.enabled_steps:
                continue
            ctx = PipelineContext(
                raw_text=text,
                text=current_text,
                config=self.config,
                span_map=span_map,
                language=current_language,
            )
            output = step.apply(ctx)
            span_map = span_map.compose(output.edits)
            transformations.extend(output.transformations)
            flags.extend(output.flags)
            if output.variants:
                current_variants.update(output.variants)
            current_text = output.text
            if ctx.language is not None:
                current_language = ctx.language

        return NormalizationResult(
            raw_text=text,
            normalized_text=current_text,
            normalized_variants=current_variants,
            transformations=transformations,
            flags=flags,
            language=current_language if current_language is not None else _EMPTY_LANGUAGE_METADATA,
            span_map=span_map,
            config_name=self.name,
            pipeline_version=PIPELINE_VERSION,
            rule_data_version={"confusables": CONFUSABLES_VERSION},
        )

    def run(self, text: str) -> NormalizationResult:
        first_pass = self._run_single_pass(text)
        if not self.config.stabilize_output:
            return first_pass

        # Stabilize output (fixpoint loop)
        combined_span_map = first_pass.span_map
        all_transformations = list(first_pass.transformations)
        all_flags = list(first_pass.flags)
        normalized_variants = dict(first_pass.normalized_variants)
        last_language = first_pass.language

        prev_text = first_pass.normalized_text
        for iter_idx in range(2, self.config.max_stabilize_iterations + 1):
            next_pass = self._run_single_pass(prev_text)
            if next_pass.normalized_text == prev_text:
                # Fully stabilized
                break

            # Remap flags from prev_text coords to original raw_text coords
            for f in next_pass.flags:
                raw_span = combined_span_map.to_raw(f.span)
                meta = dict(f.metadata)
                meta["stabilize_iteration"] = iter_idx
                all_flags.append(
                    SuspicionFlag(
                        category=f.category,
                        severity=f.severity,
                        step=f.step,
                        span=raw_span,
                        detail=f.detail,
                        metadata=meta,
                    )
                )

            # Record transformations
            for t in next_pass.transformations:
                meta = dict(t.metadata)
                meta["stabilize_iteration"] = iter_idx
                all_transformations.append(
                    Transformation(
                        step=t.step,
                        rule=t.rule,
                        original=t.original,
                        replacement=t.replacement,
                        span_before=t.span_before,
                        span_after=t.span_after,
                        metadata=meta,
                    )
                )

            # Update combined_span_map
            edits, _ = diff_edits(prev_text, next_pass.normalized_text)
            combined_span_map = combined_span_map.compose(edits)

            normalized_variants.update(next_pass.normalized_variants)
            last_language = next_pass.language
            prev_text = next_pass.normalized_text

        return NormalizationResult(
            raw_text=text,
            normalized_text=prev_text,
            normalized_variants=normalized_variants,
            transformations=all_transformations,
            flags=all_flags,
            language=last_language,
            span_map=combined_span_map,
            config_name=self.name,
            pipeline_version=PIPELINE_VERSION,
            rule_data_version={"confusables": CONFUSABLES_VERSION},
        )

    @property
    def steps(self) -> list[PipelineStep]:
        """Return a copy of the registered pipeline steps."""
        return list(self._steps)

    def _index_of(self, step_name: str) -> int:
        for i, step in enumerate(self._steps):
            if step.name == step_name:
                return i
        raise ValueError(f"no such step: {step_name!r}")

    def enable(self, step_name: str) -> None:
        """Enable a step by name."""
        self.config.enabled_steps.add(step_name)

    def disable(self, step_name: str) -> None:
        """Disable a step by name."""
        self.config.enabled_steps.discard(step_name)

    def insert_step(
        self,
        step: PipelineStep,
        *,
        after: str | None = None,
        before: str | None = None,
        enabled: bool = True,
    ) -> None:
        """Insert a step before or after an existing anchor step.

        Parameters
        ----------
        step : PipelineStep
            The custom step instance to insert.
        after : str | None
            Name of the step after which `step` will be inserted.
        before : str | None
            Name of the step before which `step` will be inserted.
        enabled : bool
            Whether to add `step.name` to `config.enabled_steps` (default True).
        """
        if (after is None) == (before is None):
            raise ValueError("insert_step requires exactly one of `after` or `before`")
        anchor = after if after is not None else before
        index = self._index_of(anchor)
        self._steps.insert(index + 1 if after is not None else index, step)
        if enabled:
            self.config.enabled_steps.add(step.name)

    def replace_step(
        self,
        step_name: str,
        step: PipelineStep,
        *,
        enabled: bool = True,
    ) -> None:
        """Replace an existing step with a new step instance.

        Parameters
        ----------
        step_name : str
            Name of the existing step to replace.
        step : PipelineStep
            The replacement step instance.
        enabled : bool
            Whether to add `step.name` to `config.enabled_steps` (default True).
        """
        idx = self._index_of(step_name)
        self._steps[idx] = step
        if enabled:
            self.config.enabled_steps.add(step.name)

    @classmethod
    def from_preset(cls, name: str) -> "NormalizationPipeline":
        from .presets import build_preset

        return build_preset(name)


Pipeline = NormalizationPipeline
