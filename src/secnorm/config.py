"""Pipeline configuration skeleton (`docs/02-architecture.md`, `docs/03`~`09`)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

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
    flag_decoded_markup: bool = False



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
    detect_latin_dialects: bool = True
    supported_languages: tuple[str, ...] | None = None


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

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["enabled_steps"] = sorted(self.enabled_steps)
        data["invisible_control"]["preserve_whitelist"] = sorted(self.invisible_control.preserve_whitelist)
        if self.obfuscation.dictionary is not None:
            data["obfuscation"]["dictionary"] = sorted(self.obfuscation.dictionary)
        return data

    def to_json(self, *, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NormalizationConfig":
        cfg = cls()
        if "enabled_steps" in data:
            cfg.enabled_steps = set(data["enabled_steps"])
        if "unicode" in data:
            cfg.unicode = UnicodeStepConfig(**data["unicode"])
        if "invisible_control" in data:
            ic = dict(data["invisible_control"])
            if "preserve_whitelist" in ic:
                ic["preserve_whitelist"] = set(ic["preserve_whitelist"])
            cfg.invisible_control = InvisibleControlStepConfig(**ic)
        if "whitespace" in data:
            cfg.whitespace = WhitespaceStepConfig(**data["whitespace"])
        if "encoding_escaping" in data:
            cfg.encoding_escaping = EncodingEscapingStepConfig(**data["encoding_escaping"])
        if "repeated_char" in data:
            cfg.repeated_char = RepeatedCharStepConfig(**data["repeated_char"])
        if "obfuscation" in data:
            ob = dict(data["obfuscation"])
            if ob.get("dictionary") is not None:
                ob["dictionary"] = frozenset(ob["dictionary"])
            cfg.obfuscation = ObfuscationStepConfig(**ob)
        if "language_structural" in data:
            ls = dict(data["language_structural"])
            if ls.get("supported_languages") is not None:
                ls["supported_languages"] = tuple(ls["supported_languages"])
            cfg.language_structural = LanguageStructuralStepConfig(**ls)
        return cfg

    @classmethod
    def from_json(cls, json_str: str) -> "NormalizationConfig":
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def from_file(cls, path: str | Path) -> "NormalizationConfig":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"config file not found: {path}")
        suffix = p.suffix.lower()
        if suffix == ".json":
            return cls.from_json(p.read_text(encoding="utf-8"))
        if suffix in (".toml", ".tml"):
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore[no-redef]
                except ImportError:
                    raise ImportError("tomllib (Python 3.11+) or tomli is required to parse TOML configuration files")
            with open(p, "rb") as f:
                data = tomllib.load(f)
            return cls.from_dict(data)
        content = p.read_text(encoding="utf-8")
        try:
            return cls.from_json(content)
        except json.JSONDecodeError:
            try:
                import tomllib
            except ImportError:
                try:
                    import tomli as tomllib  # type: ignore[no-redef]
                except ImportError:
                    raise ImportError("tomllib (Python 3.11+) or tomli is required to parse TOML configuration files")
            with open(p, "rb") as f:
                data = tomllib.load(f)
            return cls.from_dict(data)
