"""Example script demonstrating custom step plugin creation and pipeline insertion."""

import secnorm
from secnorm import Pipeline, PipelineContext, StepOutput
from secnorm.models import Span, SuspicionFlag, Transformation
from secnorm.spanmap import Edit


class SensitiveDataMaskStep:
    """A custom pipeline step that masks social security or credit card numbers."""

    name = "sensitive_data_mask"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        import re

        text = ctx.text
        # Simple pattern for 4-digit PIN / secret codes
        pattern = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{4}\b")
        matches = list(pattern.finditer(text))
        if not matches:
            return StepOutput(text=text)

        new_text = text
        transformations: list[Transformation] = []
        flags: list[SuspicionFlag] = []
        edits: list[Edit] = []

        # Process in reverse order to maintain offsets
        for match in reversed(matches):
            start, end = match.start(), match.end()
            original = match.group(0)
            replacement = "****-****-****-****"

            new_text = new_text[:start] + replacement + new_text[end:]

            src_span = Span(start, end)
            dst_span = Span(start, start + len(replacement))
            edits.append(Edit(src_span=src_span, dst_span=dst_span))

            raw_span = ctx.span_map.to_raw(src_span)
            flags.append(
                SuspicionFlag(
                    category="sensitive_pii",
                    severity="high",
                    step=self.name,
                    span=raw_span,
                    detail="Masked potential credit card number",
                )
            )
            transformations.append(
                Transformation(
                    step=self.name,
                    rule="mask_credit_card",
                    original=original,
                    replacement=replacement,
                    span_before=src_span,
                    span_after=dst_span,
                )
            )

        return StepOutput(
            text=new_text,
            transformations=transformations,
            flags=flags,
            edits=edits,
        )


def main() -> None:
    print("Secnorm Custom Step Plugin Demo\n")

    pipeline = Pipeline.from_preset("security_balanced")

    # Insert custom step after obfuscation
    pipeline.insert_step(SensitiveDataMaskStep(), after="obfuscation")

    print(f"Pipeline steps in execution order: {[s.name for s in pipeline.steps]}\n")

    sample_input = "User invoice payment card: 1234-5678-9012-3456 with discount code."
    result = pipeline.run(sample_input)

    print(f"Input text : {sample_input!r}")
    print(f"Normalized : {result.normalized_text!r}")
    print("Detected flags:")
    for flag in result.flags:
        print(f"  - [{flag.severity.upper()}] {flag.category}: {flag.detail} (span: {flag.span})")


if __name__ == "__main__":
    main()
