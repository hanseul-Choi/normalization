"""Step 6: Obfuscation normalization (docs/08-step6-obfuscation-normalization.md).

Design principle: "canonical text is conservative, matching variant is aggressive".
- Homoglyph normalization: directly reflected in canonical normalized_text.
- Separator injection & Leetspeak: reflected in normalized_variants["aggressive"].
- Encoded payload (base64/hex): detection + optional decode_and_recurse.
"""

from __future__ import annotations

import base64
import re
from typing import Any
import regex

from ..config import ObfuscationStepConfig
from ..data.confusables import CONFUSABLE_MAP
from ..diffutil import diff_edits
from ..models import Span, SuspicionFlag, Transformation
from ..pipeline import PipelineContext, StepOutput
from ..spanmap import Edit
from .language_structural_step import compute_script_ratios

_LEET_MAP: dict[str, str] = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",
}

# Regex for separator injection: 4 or more single characters separated by space, dot, dash, underscore, etc.
# Example: f.r.e.e, f r e e, f-r-e-e, f_r_e_e
_SEPARATOR_INJECTION_RE = regex.compile(
    r"(?:\b|(?<=[\s]))(?:[\p{L}\p{N}][\s._\-~*]){3,}[\p{L}\p{N}](?:\b|(?=[\s]))"
)

# Base64 payload pattern (at least 16 chars long: >=3 blocks of 4 + 1 block or padding)
_BASE64_RE = re.compile(
    r"(?:^|(?<=[\s]))(?:[A-Za-z0-9+/]{4}){3,}(?:[A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)(?=[\s]|$)"
)

# Hex payload pattern (at least 16 hex chars)
_HEX_RE = re.compile(r"(?:^|(?<=[\s]))[0-9a-fA-F]{16,}(?=[\s]|$)")


def _is_single_script_foreign_text(text: str) -> bool:
    """Return True if text consists almost purely of a single foreign alphabet (e.g. pure Russian text)."""
    ratios = compute_script_ratios(text)
    # If Latin is present alongside other scripts, it's mixed or spoofed
    if ratios.get("Latin", 0) > 0.05:
        return False

    # Check if Cyrillic or Greek alone makes up the vast majority of non-neutral chars
    cyrillic_or_greek_chars = sum(1 for ch in text if "\u0400" <= ch <= "\u052F" or "\u0370" <= ch <= "\u03FF")
    alpha_chars = sum(1 for ch in text if ch.isalpha())
    if alpha_chars > 0 and (cyrillic_or_greek_chars / alpha_chars) > 0.8:
        return True
    return False


def _apply_leetspeak(text: str) -> tuple[str, int]:
    """Apply leetspeak substitution for aggressive variant. Returns (substituted_text, count)."""
    count = 0
    chars: list[str] = []
    # Only replace leet characters when adjacent to letters or within a word token
    tokens = re.split(r"(\s+)", text)
    for tok in tokens:
        if not tok or tok.isspace():
            chars.append(tok)
            continue

        # Check if the token contains at least one letter and at least one leet char
        has_letter = any(c.isalpha() for c in tok)
        has_leet = any(c in _LEET_MAP for c in tok)
        if has_letter and has_leet:
            tok_chars: list[str] = []
            for c in tok:
                if c in _LEET_MAP:
                    tok_chars.append(_LEET_MAP[c])
                    count += 1
                else:
                    tok_chars.append(c)
            chars.append("".join(tok_chars))
        else:
            chars.append(tok)

    return "".join(chars), count


class ObfuscationStep:
    name = "obfuscation"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        cfg = ctx.config.obfuscation
        if not cfg.enabled:
            return StepOutput(text=ctx.text)

        text = ctx.text
        transformations: list[Transformation] = []
        flags: list[SuspicionFlag] = []
        edits: list[Edit] = []
        variants: dict[str, str] = {}

        # ----------------------------------------------------------------------
        # 6-1. Homoglyph normalization (Canonical normalized_text)
        # ----------------------------------------------------------------------
        canonical_text = text
        if cfg.homoglyph_normalize and not _is_single_script_foreign_text(text):
            out_chars: list[str] = []
            replaced_spans: list[tuple[int, int, str, str]] = []

            for i, ch in enumerate(text):
                if ch in CONFUSABLE_MAP:
                    repl = CONFUSABLE_MAP[ch]
                    out_chars.append(repl)
                    replaced_spans.append((i, i + 1, ch, repl))
                else:
                    out_chars.append(ch)

            if replaced_spans:
                new_text = "".join(out_chars)
                cur_pos = 0
                for start, end, orig, repl in replaced_spans:
                    span_before = Span(start, end)
                    span_after = Span(cur_pos + start, cur_pos + start + len(repl))
                    transformations.append(
                        Transformation(
                            step=self.name,
                            rule="homoglyph_normalize",
                            original=orig,
                            replacement=repl,
                            span_before=span_before,
                            span_after=span_after,
                        )
                    )
                    edits.append(Edit(span_before, span_after))
                    flags.append(
                        SuspicionFlag(
                            category="homoglyph",
                            severity="high",
                            step=self.name,
                            span=ctx.span_map.to_raw(span_before),
                            detail=f"homoglyph_{orig}_to_{repl}",
                        )
                    )
                canonical_text = new_text

        # ----------------------------------------------------------------------
        # 6-2. Separator injection detection (Aggressive variant + flag)
        # ----------------------------------------------------------------------
        aggressive_text = canonical_text
        if cfg.separator_injection_detect:
            separator_matches = list(_SEPARATOR_INJECTION_RE.finditer(canonical_text))
            for m in separator_matches:
                span_before = Span(*m.span())
                flags.append(
                    SuspicionFlag(
                        category="separator_injection",
                        severity="low",
                        step=self.name,
                        span=ctx.span_map.to_raw(span_before),
                        detail="separator_injection",
                    )
                )

            # Collapse delimiters in aggressive variant
            def _collapse_separator(match: regex.Match) -> str:
                raw_chunk = match.group(0)
                # Keep only word characters
                return regex.sub(r"[\s._\-~*]", "", raw_chunk)

            collapsed_aggressive = _SEPARATOR_INJECTION_RE.sub(_collapse_separator, aggressive_text)
            collapsed_aggressive = re.sub(r"[ ]{2,}", " ", collapsed_aggressive)

            # Check if canonical should also collapse separator
            should_collapse_canonical = cfg.separator_injection_collapse_in_canonical
            if not should_collapse_canonical and cfg.dictionary and separator_matches:
                # Check if any collapsed chunk matches dictionary
                for m in separator_matches:
                    collapsed_token = regex.sub(r"[\s._\-~*]", "", m.group(0)).lower()
                    if collapsed_token in cfg.dictionary:
                        should_collapse_canonical = True
                        break

            if should_collapse_canonical and collapsed_aggressive != canonical_text:
                c_edits, c_changes = diff_edits(canonical_text, collapsed_aggressive)
                for sb, sa, orig, repl in c_changes:
                    transformations.append(
                        Transformation(
                            step=self.name,
                            rule="collapse_separator",
                            original=orig,
                            replacement=repl,
                            span_before=sb,
                            span_after=sa,
                        )
                    )
                edits.extend(c_edits)
                canonical_text = collapsed_aggressive

            aggressive_text = collapsed_aggressive

        # ----------------------------------------------------------------------
        # 6-3. Leetspeak substitution (Aggressive variant only)
        # ----------------------------------------------------------------------
        if cfg.leetspeak_detect:
            leet_transformed, leet_count = _apply_leetspeak(aggressive_text)
            if leet_count >= 3:
                flags.append(
                    SuspicionFlag(
                        category="leetspeak",
                        severity="low",
                        step=self.name,
                        span=Span(0, len(ctx.raw_text)),
                        detail="leetspeak_sequence",
                        metadata={"count": leet_count},
                    )
                )
            aggressive_text = leet_transformed

        # ----------------------------------------------------------------------
        # 6-4. Encoded payload detection (Base64 / Hex)
        # ----------------------------------------------------------------------
        if cfg.encoded_payload_detect:
            # Base64
            for m in _BASE64_RE.finditer(canonical_text):
                candidate = m.group(0)
                span_before = Span(*m.span())
                flags.append(
                    SuspicionFlag(
                        category="encoded_payload",
                        severity="medium",
                        step=self.name,
                        span=ctx.span_map.to_raw(span_before),
                        detail="base64_payload",
                    )
                )

                # Optional decode_and_recurse
                if cfg.decode_and_recurse:
                    try:
                        decoded_bytes = base64.b64decode(candidate, validate=True)
                        if len(decoded_bytes) <= len(candidate) * cfg.max_decoded_size_ratio:
                            decoded_str = decoded_bytes.decode("utf-8")
                            # Recursive execution with safety guard
                            sub_cfg = NormalizationConfig()
                            sub_cfg.obfuscation.decode_and_recurse = False  # prevent infinite loop
                            sub_cfg.obfuscation.max_recursion_depth = cfg.max_recursion_depth - 1
                            if cfg.max_recursion_depth > 0:
                                from ..presets import build_preset

                                sub_pipe = build_preset("security_balanced")
                                sub_pipe.config = sub_cfg
                                sub_res = sub_pipe.run(decoded_str)
                                for f in sub_res.flags:
                                    flags.append(
                                        SuspicionFlag(
                                            category=f.category,
                                            severity=f.severity,
                                            step=self.name,
                                            span=ctx.span_map.to_raw(span_before),
                                            detail=f"decoded_payload:{f.detail}",
                                            metadata={"source": "decoded_payload", "depth": 1},
                                        )
                                    )
                    except Exception:
                        pass

            # Hex
            for m in _HEX_RE.finditer(canonical_text):
                span_before = Span(*m.span())
                flags.append(
                    SuspicionFlag(
                        category="encoded_payload",
                        severity="medium",
                        step=self.name,
                        span=ctx.span_map.to_raw(span_before),
                        detail="hex_payload",
                    )
                )

        # Set aggressive variant if it differs from canonical_text
        if aggressive_text != canonical_text:
            variants["aggressive"] = aggressive_text

        return StepOutput(
            text=canonical_text,
            transformations=transformations,
            flags=flags,
            edits=edits,
            variants=variants,
        )
