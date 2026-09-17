from secnorm.config import NormalizationConfig
from secnorm.models import Span
from secnorm.pipeline import PipelineContext
from secnorm.spanmap import SpanMap
from secnorm.steps import UnicodeStep


def _run(text: str, form: str = "NFKC"):
    config = NormalizationConfig()
    config.unicode.form = form
    ctx = PipelineContext(
        raw_text=text, text=text, config=config, span_map=SpanMap.identity(len(text))
    )
    return UnicodeStep().apply(ctx)


def test_fullwidth_alnum_collapses_to_ascii():
    output = _run("Ａｄｍｉｎ")
    assert output.text == "Admin"
    assert output.transformations[0].rule == "normalize_NFKC"


def test_circled_numbers_collapse_to_ascii_digits():
    output = _run("① ② ③")
    assert output.text == "1 2 3"
    assert [t.original for t in output.transformations] == ["①", "②", "③"]


def test_halfwidth_katakana_expands_to_fullwidth():
    output = _run("ｶﾀｶﾅ")
    assert output.text == "カタカナ"


def test_ligature_decomposes():
    output = _run("ﬁle")
    assert output.text == "file"


def test_no_change_returns_empty_transformations():
    output = _run("hello world")
    assert output.text == "hello world"
    assert output.transformations == []
    assert output.edits == []


def test_nfc_form_leaves_compatibility_chars_alone():
    output = _run("Ａ", form="NFC")
    assert output.text == "Ａ"
    assert output.transformations == []


def test_span_before_after_use_step_local_coordinates():
    output = _run("x①y")
    (t,) = output.transformations
    assert t.span_before == Span(1, 2)
    assert t.span_after == Span(1, 2)
