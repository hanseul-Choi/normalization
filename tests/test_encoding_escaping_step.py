from secnorm.config import EncodingEscapingStepConfig, NormalizationConfig
from secnorm.models import Span
from secnorm.pipeline import PipelineContext
from secnorm.spanmap import Edit, SpanMap
from secnorm.steps import EncodingEscapingStep


def _run(text: str, cfg: EncodingEscapingStepConfig | None = None, span_map=None):
    config = NormalizationConfig(encoding_escaping=cfg or EncodingEscapingStepConfig())
    span_map = span_map if span_map is not None else SpanMap.identity(len(text))
    ctx = PipelineContext(raw_text=text, text=text, config=config, span_map=span_map)
    return EncodingEscapingStep().apply(ctx)


def test_html_entity_decoded_without_flag():
    output = _run("AT&amp;T")
    assert output.text == "AT&T"
    assert output.flags == []
    assert output.transformations[0].rule == "decode_html_entity"


def test_url_percent_encoding_decoded_in_url_context():
    output = _run("https://example.com/%ED%95%9C%EA%B8%80")
    assert output.text == "https://example.com/한글"
    assert output.flags == []


def test_percent_encoding_outside_url_is_flagged_not_decoded():
    output = _run("100%20 discount")
    assert output.text == "100%20 discount"
    assert output.transformations == []
    assert len(output.flags) == 1
    flag = output.flags[0]
    assert flag.category == "encoded_payload"
    assert flag.severity == "low"
    assert flag.span == Span(3, 6)


def test_url_decoding_off_leaves_text_and_flags_untouched():
    cfg = EncodingEscapingStepConfig(decode_url_encoding="off")
    output = _run("100%20 discount", cfg=cfg)
    assert output.text == "100%20 discount"
    assert output.flags == []


def test_url_decoding_always_decodes_even_outside_url_context():
    cfg = EncodingEscapingStepConfig(decode_url_encoding="always")
    output = _run("100%20 discount", cfg=cfg)
    assert output.text == "100  discount"
    assert len(output.flags) == 1
    assert output.flags[0].category == "encoded_payload"
    assert output.flags[0].severity == "medium"



def test_unicode_escape_decoded_and_flagged():
    output = _run("안\\uB155")
    assert output.text == "안녕"
    flag = output.flags[0]
    assert flag.category == "encoded_payload"
    assert flag.severity == "medium"
    assert flag.detail == "unicode_escape_sequence"
    assert output.transformations[0].rule == "decode_unicode_escape"


def test_unicode_escape_flag_only_does_not_decode():
    cfg = EncodingEscapingStepConfig(unicode_escape_policy="flag_only")
    output = _run("안\\uB155", cfg=cfg)
    assert output.text == "안\\uB155"
    assert output.transformations == []
    assert len(output.flags) == 1


def test_unicode_escape_ignore_policy_does_nothing():
    cfg = EncodingEscapingStepConfig(unicode_escape_policy="ignore")
    output = _run("안\\uB155", cfg=cfg)
    assert output.text == "안\\uB155"
    assert output.transformations == []
    assert output.flags == []


def test_invalid_unicode_escape_is_left_untouched():
    output = _run("\\uZZZZ")
    assert output.text == "\\uZZZZ"


def test_no_change_returns_empty_output():
    output = _run("plain text, nothing special")
    assert output.text == "plain text, nothing special"
    assert output.transformations == []
    assert output.flags == []
    assert output.edits == []


def test_flag_span_is_mapped_through_prior_step_edits_to_raw_coordinates():
    raw_text = "X100%20 discount"
    span_map = SpanMap.identity(len(raw_text)).compose([Edit(Span(0, 1), Span(0, 0))])
    output = _run("100%20 discount", span_map=span_map)
    assert output.flags[0].span == Span(4, 7)


def test_chained_html_then_url_decode_produces_correct_final_span():
    # &#37; decodes to '%', which together with the following '20' then
    # looks like a percent-encoded sequence once inside a URL: the two
    # sub-transforms chain (html decode runs first, url decode second).
    output = _run("https://example.com/a&#37;20b")
    assert output.text == "https://example.com/a b"
    assert {t.rule for t in output.transformations} == {
        "decode_html_entity",
        "decode_url_percent_encoding",
    }


def test_url_decode_always_mode_flags_percent_encodings():
    output = _run(
        "%3Cscript%3Ealert(1)%3C/script%3E",
        cfg=EncodingEscapingStepConfig(decode_url_encoding="always"),
    )
    assert output.text == "<script>alert(1)</script>"
    assert len(output.flags) == 4
    assert all(f.category == "encoded_payload" for f in output.flags)
    assert all(f.severity == "medium" for f in output.flags)
    assert all(f.detail == "percent_encoding_decoded_always_mode" for f in output.flags)


def test_security_strict_url_decoding_risk_action():
    import secnorm

    res = secnorm.normalize("..%2f..%2fetc%2fpasswd", preset="security_strict")
    assert res.normalized_text == "../../etc/passwd"
    assert len(res.flags) > 0
    report = res.evaluate_risk()
    assert report.recommended_action != "allow"

