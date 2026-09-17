from secnorm.config import NormalizationConfig, RepeatedCharStepConfig
from secnorm.models import Span
from secnorm.pipeline import PipelineContext
from secnorm.spanmap import SpanMap
from secnorm.steps.repeated_char_step import RepeatedCharStep


def _ctx(text: str, cfg: RepeatedCharStepConfig | None = None) -> PipelineContext:
    config = NormalizationConfig()
    if cfg is not None:
        config.repeated_char = cfg
    return PipelineContext(
        raw_text=text,
        text=text,
        config=config,
        span_map=SpanMap.identity(len(text)),
    )


def test_golden_cases_from_spec():
    step = RepeatedCharStep()

    # 1. Latin / general word
    out = step.apply(_ctx("coooooool"))
    assert out.text == "cool"
    assert len(out.transformations) == 1
    assert out.transformations[0].metadata == {"original_count": 7, "collapsed_to": 2, "char": "o"}
    assert len(out.flags) == 1
    assert out.flags[0].category == "excessive_repetition"
    assert out.flags[0].severity == "low"

    # 2. Hangul standalone jamo
    out_jamo = step.apply(_ctx("ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ"))
    assert out_jamo.text == "ㅋㅋㅋ"
    assert out_jamo.transformations[0].metadata["collapsed_to"] == 3
    assert out_jamo.flags[0].category == "excessive_repetition"

    # 3. Punctuation
    out_punct = step.apply(_ctx("대박!!!!!!!!"))
    assert out_punct.text == "대박!!!"
    assert out_punct.transformations[0].metadata["collapsed_to"] == 3


def test_emoji_repetition_collapse():
    step = RepeatedCharStep()
    out = step.apply(_ctx("축하해요 😂😂😂😂😂😂 최고"))
    assert out.text == "축하해요 😂😂😂 최고"
    assert len(out.transformations) == 1
    assert out.transformations[0].metadata["collapsed_to"] == 3
    assert len(out.flags) == 1


def test_normal_double_letters_are_preserved():
    step = RepeatedCharStep()
    for word in ("cool", "see", "쓰레기", "ㅋㅋㅋ", "!!!", "😂😂😂"):
        out = step.apply(_ctx(word))
        assert out.text == word
        assert len(out.transformations) == 0
        assert len(out.flags) == 0


def test_whitespace_is_ignored_by_repeated_char_step():
    step = RepeatedCharStep()
    text = "hello       world"
    out = step.apply(_ctx(text))
    # RepeatedCharStep does not collapse whitespace (WhitespaceStep's job)
    assert out.text == text
    assert len(out.transformations) == 0


def test_min_run_length_to_flag_threshold():
    step = RepeatedCharStep()
    # 4 repetitions: collapsed (cap=2) but count < 5 so NO flag
    out_4 = step.apply(_ctx("sooooper"))
    assert out_4.text == "sooper"
    assert len(out_4.transformations) == 1
    assert len(out_4.flags) == 0

    # 5 repetitions: collapsed AND flagged
    out_5 = step.apply(_ctx("soooooper"))
    assert out_5.text == "sooper"
    assert len(out_5.flags) == 1


def test_category_overrides():
    cfg = RepeatedCharStepConfig(category_overrides={"default": 1, "jamo": 1})
    step = RepeatedCharStep()
    out = step.apply(_ctx("coool ㅋㅋㅋ", cfg=cfg))
    assert out.text == "col ㅋ"


def test_flag_span_maps_to_raw_coordinates():
    step = RepeatedCharStep()
    text = "prefix coooooool suffix"
    raw_text = "ORIGINAL prefix coooooool suffix"
    # Create span map with an initial offset of 9
    from secnorm.spanmap import Edit

    initial_map = SpanMap.identity(len(raw_text)).compose([Edit(Span(0, 9), Span(0, 0))])
    ctx = PipelineContext(
        raw_text=raw_text,
        text=text,
        config=NormalizationConfig(),
        span_map=initial_map,
    )
    out = step.apply(ctx)
    assert len(out.flags) == 1
    flag = out.flags[0]
    assert raw_text[flag.span.start : flag.span.end] == "ooooooo"
