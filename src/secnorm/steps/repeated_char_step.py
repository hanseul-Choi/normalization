"""Step 5: repeated-character normalization (docs/07-step5-repeated-characters.md)."""

from __future__ import annotations

import unicodedata
import regex

from ..config import RepeatedCharStepConfig
from ..models import Span, SuspicionFlag, Transformation
from ..pipeline import PipelineContext, StepOutput
from ..spanmap import Edit

try:
    import unicodedata2 as unicodedata  # type: ignore[no-redef]
except ImportError:
    pass

try:
    import emoji

    def _is_emoji(cluster: str) -> bool:
        return emoji.is_emoji(cluster)
except ImportError:
    def _is_emoji(cluster: str) -> bool:
        return any(unicodedata.category(c) == "So" for c in cluster)


def _is_whitespace(cluster: str) -> bool:
    if cluster in (" ", "\t", "\n", "\r"):
        return True
    if len(cluster) == 1 and unicodedata.category(cluster).startswith("Z"):
        return True
    return False


def _is_hangul_jamo(cluster: str) -> bool:
    if len(cluster) == 1:
        cp = ord(cluster)
        return (
            (0x3131 <= cp <= 0x318E)  # Hangul Compatibility Jamo
            or (0x1100 <= cp <= 0x11FF)  # Hangul Jamo
            or (0xA960 <= cp <= 0xA97C)  # Hangul Jamo Extended-A
            or (0xD7B0 <= cp <= 0xD7FB)  # Hangul Jamo Extended-B
        )
    return False


def _is_punctuation_or_symbol(cluster: str) -> bool:
    cat = unicodedata.category(cluster[0])
    return cat.startswith("P") or cat in ("Sm", "Sc", "Sk", "So")


def _get_cap(cluster: str, cfg: RepeatedCharStepConfig) -> int | None:
    if _is_whitespace(cluster):
        return None

    if _is_emoji(cluster):
        return cfg.category_overrides.get("emoji", cfg.emoji_cap)

    if _is_hangul_jamo(cluster):
        return cfg.category_overrides.get("jamo", cfg.jamo_cap)

    if _is_punctuation_or_symbol(cluster):
        return cfg.category_overrides.get("punctuation", cfg.punctuation_cap)

    return cfg.category_overrides.get("default", cfg.default_cap)


class RepeatedCharStep:
    name = "repeated_char"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        cfg = ctx.config.repeated_char
        text = ctx.text

        if not text:
            return StepOutput(text=text)

        matches = list(regex.finditer(r"\X", text))
        if not matches:
            return StepOutput(text=text)

        # Unpack clusters that consist purely of repeated conjoining jamo
        clusters: list[tuple[str, int, int]] = []
        for m in matches:
            cluster = m.group(0)
            start, end = m.span()
            if len(cluster) > 1 and len(set(cluster)) == 1 and _is_hangul_jamo(cluster[0]):
                c = cluster[0]
                cur = start
                for _ in range(len(cluster)):
                    clusters.append((c, cur, cur + 1))
                    cur += 1
            else:
                clusters.append((cluster, start, end))

        out_pieces: list[str] = []
        transformations: list[Transformation] = []
        flags: list[SuspicionFlag] = []
        edits: list[Edit] = []

        out_pos = 0

        # Group consecutive identical clusters
        i = 0
        n_clusters = len(clusters)
        while i < n_clusters:
            cluster_text, run_start, run_end = clusters[i]
            run_count = 1

            j = i + 1
            while j < n_clusters and clusters[j][0] == cluster_text:
                run_end = clusters[j][2]
                run_count += 1
                j += 1

            cap = _get_cap(cluster_text, cfg)
            if cap is not None and run_count > cap:
                collapsed = cluster_text * cap
                span_before = Span(run_start, run_end)
                span_after = Span(out_pos, out_pos + len(collapsed))

                transformations.append(
                    Transformation(
                        step=self.name,
                        rule="collapse_run",
                        original=text[run_start:run_end],
                        replacement=collapsed,
                        span_before=span_before,
                        span_after=span_after,
                        metadata={
                            "original_count": run_count,
                            "collapsed_to": cap,
                            "char": cluster_text,
                        },
                    )
                )
                edits.append(Edit(span_before, span_after))

                if run_count >= cfg.min_run_length_to_flag:
                    flags.append(
                        SuspicionFlag(
                            category="excessive_repetition",
                            severity="low",
                            step=self.name,
                            span=ctx.span_map.to_raw(span_before),
                            detail=f"repeated_{cluster_text}",
                            metadata={"run_count": run_count, "cap": cap},
                        )
                    )

                out_pieces.append(collapsed)
                out_pos += len(collapsed)
            else:
                raw_chunk = text[run_start:run_end]
                out_pieces.append(raw_chunk)
                out_pos += len(raw_chunk)

            i = j

        new_text = "".join(out_pieces)
        if new_text == text:
            return StepOutput(text=text)

        return StepOutput(
            text=new_text,
            transformations=transformations,
            flags=flags,
            edits=edits,
        )
