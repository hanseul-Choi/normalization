"""Step 7: Language and structural metadata extraction (docs/09-step7-language-structural-metadata.md).

Also provides standalone script-ratio extraction usable as a prepass for Step 6.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..config import LanguageStructuralStepConfig
from ..models import LanguageMetadata, StructuralHints
from ..pipeline import PipelineContext, StepOutput

try:
    import unicodedata2 as unicodedata  # type: ignore[no-redef]
except ImportError:
    pass

# Script code point ranges (v1 scope: Hangul, Latin, Han, Hiragana, Katakana)
def _classify_script(cp: int) -> str:
    # Hangul
    if (
        (0xAC00 <= cp <= 0xD7AF)
        or (0x1100 <= cp <= 0x11FF)
        or (0x3130 <= cp <= 0x318F)
        or (0xA960 <= cp <= 0xA97F)
        or (0xD7B0 <= cp <= 0xD7FF)
    ):
        return "Hangul"

    # Hiragana
    if 0x3040 <= cp <= 0x309F:
        return "Hiragana"

    # Katakana
    if (0x30A0 <= cp <= 0x30FF) or (0x31F0 <= cp <= 0x31FF):
        return "Katakana"

    # Han (CJK Unified Ideographs & compatibility)
    if (
        (0x4E00 <= cp <= 0x9FFF)
        or (0x3400 <= cp <= 0x4DBF)
        or (0x20000 <= cp <= 0x2A6DF)
        or (0xF900 <= cp <= 0xFAFF)
    ):
        return "Han"

    # Latin
    if (
        (0x0041 <= cp <= 0x005A)
        or (0x0061 <= cp <= 0x007A)
        or (0x00C0 <= cp <= 0x024F)
        or (0x2C60 <= cp <= 0x2C7F)
        or (0xA720 <= cp <= 0xA7FF)
        or (0xAB30 <= cp <= 0xAB6F)
    ):
        return "Latin"

    # Cyrillic
    if (0x0400 <= cp <= 0x04FF) or (0x0500 <= cp <= 0x052F) or (0x2DE0 <= cp <= 0x2DFF):
        return "Cyrillic"

    # Greek
    if (0x0370 <= cp <= 0x03FF) or (0x1F00 <= cp <= 0x1FFF):
        return "Greek"

    # Arabic
    if (0x0600 <= cp <= 0x06FF) or (0x0750 <= cp <= 0x077F) or (0x08A0 <= cp <= 0x08FF):
        return "Arabic"

    ch = chr(cp)
    cat = unicodedata.category(ch)
    if cat.startswith("Z") or cat.startswith("P") or cat.startswith("N") or cat.startswith("C") or cat.startswith("S"):
        return "Common"

    return "Other"


def compute_script_ratios(text: str) -> dict[str, float]:
    """Compute relative frequencies of unicode scripts in the text."""
    if not text:
        return {}

    counts: dict[str, int] = {}
    for ch in text:
        s = _classify_script(ord(ch))
        counts[s] = counts.get(s, 0) + 1

    total = len(text)
    return {s: round(cnt / total, 4) for s, cnt in sorted(counts.items(), key=lambda x: -x[1])}


def check_mixed_script(counts: dict[str, int], threshold: float = 0.15) -> bool:
    """Return True if the top 2 non-neutral scripts both exceed `threshold`."""
    script_counts = {s: cnt for s, cnt in counts.items() if s not in ("Common", "Other")}
    total_script_chars = sum(script_counts.values())
    if total_script_chars == 0:
        return False

    sorted_ratios = sorted([cnt / total_script_chars for cnt in script_counts.values()], reverse=True)
    if len(sorted_ratios) >= 2 and sorted_ratios[0] >= threshold and sorted_ratios[1] >= threshold:
        return True
    return False


def detect_language(
    text: str,
    counts: dict[str, int],
    cfg: LanguageStructuralStepConfig,
) -> tuple[str | None, float]:
    """Hybrid language detection (rule-based with CJK markers and optional langdetect fallback for ja/zh)."""
    clean_len = sum(
        counts.get(s, 0)
        for s in ("Hangul", "Latin", "Han", "Hiragana", "Katakana", "Cyrillic", "Greek", "Arabic")
    )
    if clean_len < cfg.min_text_length_for_detection:
        return None, 0.0

    hangul = counts.get("Hangul", 0)
    hiragana = counts.get("Hiragana", 0)
    katakana = counts.get("Katakana", 0)
    han = counts.get("Han", 0)
    latin = counts.get("Latin", 0)
    cyrillic = counts.get("Cyrillic", 0)
    greek = counts.get("Greek", 0)
    arabic = counts.get("Arabic", 0)

    # Rule 1: Japanese kana present -> Japanese (Hanzi in Japanese is normal)
    if hiragana > 0 or katakana > 0:
        return "ja", 0.95

    # Rule 2: Hangul dominant -> Korean
    if hangul > 0 and hangul >= (clean_len * 0.3):
        return "ko", 0.95

    # Rule 3: Latin dominant -> English
    if latin > 0 and latin >= (clean_len * 0.5):
        return "en", 0.90

    # Rule 3b: Cyrillic / Greek / Arabic dominant
    if cyrillic > 0 and cyrillic >= (clean_len * 0.5):
        return "ru", 0.90
    if greek > 0 and greek >= (clean_len * 0.5):
        return "el", 0.90
    if arabic > 0 and arabic >= (clean_len * 0.5):
        return "ar", 0.90

    # Rule 4: Pure Han characters (ja vs zh ambiguity)
    if han > 0 and hangul == 0 and hiragana == 0 and katakana == 0:
        # 4a. CJK specific character heuristics (Kokuji/Shinjitai vs Simplified Chinese)
        from ..data import (
            JAPANESE_SPECIFIC_HAN,
            SIMPLIFIED_CHINESE_SPECIFIC_HAN,
            TRADITIONAL_CHINESE_SPECIFIC_HAN,
        )

        has_ja_marker = any(ch in JAPANESE_SPECIFIC_HAN for ch in text)
        has_zh_marker = any(
            ch in SIMPLIFIED_CHINESE_SPECIFIC_HAN or ch in TRADITIONAL_CHINESE_SPECIFIC_HAN
            for ch in text
        )

        if has_ja_marker and not has_zh_marker:
            return "ja", 0.95
        if has_zh_marker and not has_ja_marker:
            return "zh", 0.95

        # 4b. Secondary fallback to langdetect if markers are inconclusive
        if cfg.fallback_detector == "langdetect":
            try:
                import langdetect
                from langdetect import DetectorFactory

                # Deterministic seed for langdetect
                DetectorFactory.seed = 0
                langs = langdetect.detect_langs(text)
                if langs:
                    best = langs[0]
                    lang_code = best.lang.lower()
                    if lang_code in ("zh-cn", "zh-tw", "zh"):
                        return "zh", round(best.prob, 2)
                    if lang_code == "ja":
                        return "ja", round(best.prob, 2)
                    if lang_code in ("ko", "en"):
                        return lang_code, round(best.prob, 2)
            except Exception:
                pass
        return None, 0.0

    return None, 0.0


_HTML_TAG_RE = re.compile(r"<[a-zA-Z][^>]*>")
_MARKDOWN_RE = re.compile(
    r"(\*\*|__).*?\1|`[^`]+`|^#+\s+|\[.*?\]\(https?://\S+\)|^[-*+]\s+",
    re.MULTILINE,
)
_URL_RE = re.compile(
    r"https?://\S+|\b(?:[a-z0-9-]+\.)+(?:com|org|net|io|edu|gov|kr|jp|cn|me|ai|app)\b(?:/\S*)?",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_CODE_BLOCK_RE = re.compile(
    r"```[\s\S]*?```|^(?: {4}|\t)[^\n]+(?:\n(?: {4}|\t)[^\n]+)*",
    re.MULTILINE,
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?。！？\n]+")
_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def extract_structural_hints(text: str) -> StructuralHints:
    has_html = bool(_HTML_TAG_RE.search(text))
    has_markdown = bool(_MARKDOWN_RE.search(text))
    has_url = bool(_URL_RE.search(text))
    has_email = bool(_EMAIL_RE.search(text))
    has_code_block = bool(_CODE_BLOCK_RE.search(text))

    # Sentence count
    raw_sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    sentence_count = len(raw_sentences)

    # Word count: spaces + CJK characters
    cjk_char_count = sum(
        1 for ch in text if _classify_script(ord(ch)) in ("Han", "Hiragana", "Katakana")
    )
    non_cjk_words = len(_WORD_RE.findall(text))
    # Combine word tokens with single CJK characters to approximate count
    word_count = non_cjk_words + cjk_char_count

    return StructuralHints(
        has_html=has_html,
        has_markdown=has_markdown,
        has_url=has_url,
        has_email=has_email,
        has_code_block=has_code_block,
        sentence_count=sentence_count,
        word_count=word_count,
        direction="ltr",
    )


class LanguageStructuralStep:
    name = "language_structural"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        cfg = ctx.config.language_structural
        text = ctx.text

        if not cfg.enabled:
            return StepOutput(text=text)

        counts: dict[str, int] = {}
        for ch in text:
            s = _classify_script(ord(ch))
            counts[s] = counts.get(s, 0) + 1

        total = len(text)
        script_ratios = {s: round(cnt / total, 4) for s, cnt in sorted(counts.items(), key=lambda x: -x[1])} if total > 0 else {}
        is_mixed = check_mixed_script(counts, cfg.mixed_script_threshold)
        primary_lang, conf = detect_language(text, counts, cfg)
        structural = extract_structural_hints(text)

        ctx.language = LanguageMetadata(
            primary_language=primary_lang,
            language_confidence=conf,
            script_ratios=script_ratios,
            is_mixed_script=is_mixed,
            structural=structural,
        )

        return StepOutput(text=text)
