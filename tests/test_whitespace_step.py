from secnorm.config import NormalizationConfig, WhitespaceStepConfig
from secnorm.pipeline import PipelineContext
from secnorm.spanmap import SpanMap
from secnorm.steps import WhitespaceStep


def _run(text: str, cfg: WhitespaceStepConfig | None = None):
    config = NormalizationConfig(whitespace=cfg or WhitespaceStepConfig())
    ctx = PipelineContext(
        raw_text=text, text=text, config=config, span_map=SpanMap.identity(len(text))
    )
    return WhitespaceStep().apply(ctx)


def test_repeated_spaces_collapse_to_one():
    output = _run("무료   상담  가능")
    assert output.text == "무료 상담 가능"


def test_ideographic_space_becomes_ascii_space_by_default():
    output = _run("안녕　하세요")
    assert output.text == "안녕 하세요"


def test_ideographic_space_preserved_when_configured():
    output = _run("안녕　하세요", cfg=WhitespaceStepConfig(preserve_ideographic_space=True))
    assert output.text == "안녕　하세요"
    assert output.transformations == []


def test_strict_mode_collapses_newlines_to_single_space():
    output = _run("줄바꿈\n\n\n\n많음", cfg=WhitespaceStepConfig(mode="strict"))
    assert output.text == "줄바꿈 많음"


def test_structural_mode_caps_newlines_at_two():
    output = _run("줄바꿈\n\n\n\n많음", cfg=WhitespaceStepConfig(mode="structural"))
    assert output.text == "줄바꿈\n\n많음"


def test_structural_mode_still_collapses_repeated_spaces():
    output = _run("a   b", cfg=WhitespaceStepConfig(mode="structural"))
    assert output.text == "a b"


def test_nbsp_and_various_width_spaces_become_ascii_space():
    output = _run("a b c d")
    assert output.text == "a b c d"


def test_trim_edges_strips_leading_and_trailing_whitespace():
    output = _run("  hello  ")
    assert output.text == "hello"


def test_trim_edges_disabled_keeps_edges():
    output = _run("  hello  ", cfg=WhitespaceStepConfig(trim_edges=False))
    assert output.text == " hello "


def test_tab_kept_when_policy_is_keep_and_isolated():
    output = _run("a\tb", cfg=WhitespaceStepConfig(tab_policy="keep"))
    assert output.text == "a\tb"


def test_tab_converted_to_space_by_default():
    output = _run("a\tb")
    assert output.text == "a b"


def test_no_change_returns_empty_transformations():
    output = _run("clean text")
    assert output.text == "clean text"
    assert output.transformations == []
    assert output.edits == []


def test_line_and_paragraph_separators_become_newline():
    output = _run("a b", cfg=WhitespaceStepConfig(mode="structural", trim_edges=False))
    assert output.text == "a\nb"
