from secnorm.config import NormalizationConfig
from secnorm.pipeline import PipelineContext
from secnorm.spanmap import SpanMap
from secnorm.steps.language_structural_step import (
    LanguageStructuralStep,
    compute_script_ratios,
    check_mixed_script,
    extract_structural_hints,
)


def _ctx(text: str) -> PipelineContext:
    return PipelineContext(
        raw_text=text,
        text=text,
        config=NormalizationConfig(),
        span_map=SpanMap.identity(len(text)),
    )


def test_compute_script_ratios():
    ratios = compute_script_ratios("안녕하세요 Hello 123")
    assert "Hangul" in ratios
    assert "Latin" in ratios
    assert "Common" in ratios
    assert ratios["Hangul"] > 0
    assert ratios["Latin"] > 0


def test_mixed_script_detection():
    # 50% Korean, 50% English (excluding Common) -> mixed script
    counts_mixed = {"Hangul": 5, "Latin": 5, "Common": 2}
    assert check_mixed_script(counts_mixed, threshold=0.15) is True

    # 95% Korean, 5% English -> NOT mixed script
    counts_pure = {"Hangul": 95, "Latin": 5, "Common": 20}
    assert check_mixed_script(counts_pure, threshold=0.15) is False


def test_language_detection_rules():
    step = LanguageStructuralStep()

    # Korean
    ctx_ko = _ctx("안녕하세요 반갑습니다!")
    step.apply(ctx_ko)
    assert ctx_ko.language is not None
    assert ctx_ko.language.primary_language == "ko"
    assert ctx_ko.language.language_confidence >= 0.9

    # Japanese with kana
    ctx_ja = _ctx("これは日本語のテストです")
    step.apply(ctx_ja)
    assert ctx_ja.language is not None
    assert ctx_ja.language.primary_language == "ja"

    # English
    ctx_en = _ctx("This is a simple English sentence.")
    step.apply(ctx_en)
    assert ctx_en.language is not None
    assert ctx_en.language.primary_language == "en"


def test_structural_hints_extraction():
    text = (
        "# Title\n"
        "Here is **bold** and `code`.\n"
        "Visit https://example.com or email test@example.com\n"
        "<div>HTML tag</div>\n"
        "```python\nprint('hello')\n```"
    )
    hints = extract_structural_hints(text)
    assert hints.has_html is True
    assert hints.has_markdown is True
    assert hints.has_url is True
    assert hints.has_email is True
    assert hints.has_code_block is True
    assert hints.sentence_count >= 2
    assert hints.word_count > 5
    assert hints.direction == "ltr"


def test_step_leaves_text_unchanged():
    step = LanguageStructuralStep()
    text = "Hello world!"
    ctx = _ctx(text)
    out = step.apply(ctx)
    assert out.text == text
    assert len(out.transformations) == 0
    assert len(out.flags) == 0
    assert ctx.language is not None
    assert ctx.language.primary_language == "en"
