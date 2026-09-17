"""Pipeline configuration skeleton (`docs/02-architecture.md`, `docs/03`~`09`)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ALL_STEP_NAMES = (
    "unicode",
    "invisible_control",
    "whitespace",
    "encoding_escaping",
    "repeated_char",
    "obfuscation",
    "language_structural",
)


@dataclass
class UnicodeStepConfig:
    form: Literal["NFC", "NFD", "NFKC", "NFKD"] = "NFKC"


@dataclass
class InvisibleControlStepConfig:
    strip_control: bool = True
    strip_zero_width: bool = True
    strip_bidi_override: bool = True
    strip_tag_chars: bool = True
    strip_variation_selectors: Literal["suspicious_only", "all", "none"] = "suspicious_only"
    strip_unassigned: bool = True
    private_use_policy: Literal["keep", "flag", "strip"] = "flag"
    preserve_whitelist: set[str] = field(default_factory=lambda: {"\t", "\n"})


@dataclass
class WhitespaceStepConfig:
    mode: Literal["strict", "structural"] = "strict"
    preserve_ideographic_space: bool = False
    tab_policy: Literal["to_space", "keep"] = "to_space"
    trim_edges: bool = True


@dataclass
class EncodingEscapingStepConfig:
    decode_html_entities: bool = True
    decode_url_encoding: Literal["url_context_only", "always", "off"] = "url_context_only"
    unicode_escape_policy: Literal["decode_and_flag", "flag_only", "ignore"] = "decode_and_flag"
    mojibake_repair: bool = False


@dataclass
class RepeatedCharStepConfig:
    default_cap: int = 2
    jamo_cap: int = 3
    punctuation_cap: int = 3
    emoji_cap: int = 3
    min_run_length_to_flag: int = 5
    category_overrides: dict[str, int] = field(default_factory=dict)


@dataclass
class ObfuscationStepConfig:
    enabled: bool = True
    homoglyph_normalize: bool = True
    separator_injection_detect: bool = True
    separator_injection_collapse_in_canonical: bool = False
    leetspeak_detect: bool = True
    encoded_payload_detect: bool = True
    decode_and_recurse: bool = False
    max_recursion_depth: int = 1
    max_decoded_size_ratio: float = 10.0
    dictionary: frozenset[str] | None = None


@dataclass
class LanguageStructuralStepConfig:
    enabled: bool = True
    mixed_script_threshold: float = 0.15
    fallback_detector: Literal["langdetect", "none"] = "langdetect"
    min_text_length_for_detection: int = 2


@dataclass
class NormalizationConfig:
    enabled_steps: set[str] = field(default_factory=lambda: set(ALL_STEP_NAMES))
    unicode: UnicodeStepConfig = field(default_factory=UnicodeStepConfig)
    invisible_control: InvisibleControlStepConfig = field(default_factory=InvisibleControlStepConfig)
    whitespace: WhitespaceStepConfig = field(default_factory=WhitespaceStepConfig)
    encoding_escaping: EncodingEscapingStepConfig = field(default_factory=EncodingEscapingStepConfig)
    repeated_char: RepeatedCharStepConfig = field(default_factory=RepeatedCharStepConfig)
    obfuscation: ObfuscationStepConfig = field(default_factory=ObfuscationStepConfig)
    language_structural: LanguageStructuralStepConfig = field(default_factory=LanguageStructuralStepConfig)
