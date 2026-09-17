from secnorm.models import Span
from secnorm.spanmap import Edit, SpanMap


def test_identity_map_roundtrips():
    span_map = SpanMap.identity(5)
    assert span_map.to_raw(Span(1, 3)) == Span(1, 3)
    assert span_map.to_normalized(Span(1, 3)) == Span(1, 3)


def test_deletion_shifts_trailing_unchanged_region():
    # "ab​cd" -> "abcd": drop the zero-width char at raw index 2.
    span_map = SpanMap.identity(5).compose([Edit(Span(2, 3), Span(2, 2))])

    # unchanged prefix "ab" stays identity
    assert span_map.to_raw(Span(0, 2)) == Span(0, 2)
    # "cd" (normalized 2..4) shifted back to raw "cd" (raw 3..5)
    assert span_map.to_raw(Span(2, 4)) == Span(3, 5)
    assert span_map.to_raw(Span(2, 3)) == Span(3, 4)
    assert span_map.to_raw(Span(3, 4)) == Span(4, 5)


def test_insertion_expands_normalized_text():
    # "a&b" -> "a&amp;b" style expansion (dst wider than src).
    span_map = SpanMap.identity(3).compose([Edit(Span(1, 2), Span(1, 6))])

    assert span_map.to_raw(Span(0, 1)) == Span(0, 1)
    # the whole expanded region blobs back to the single raw char it replaced
    assert span_map.to_raw(Span(1, 6)) == Span(1, 2)
    assert span_map.to_raw(Span(3, 4)) == Span(1, 2)
    # trailing "b" shifts from raw index 2 to normalized index 6
    assert span_map.to_raw(Span(6, 7)) == Span(2, 3)


def test_pure_insertion_anchors_to_raw_point():
    # "" inserted between raw index 1 and 2, e.g. adding a separator.
    span_map = SpanMap.identity(4).compose([Edit(Span(2, 2), Span(2, 5))])

    assert span_map.to_raw(Span(2, 5)) == Span(2, 2)
    assert span_map.to_raw(Span(0, 2)) == Span(0, 2)
    assert span_map.to_raw(Span(5, 7)) == Span(2, 4)


def test_compose_chains_across_multiple_steps():
    # Step 1: NFKC widens "Ａ" (1 char) -> "A" (1 char); no-op length-wise.
    # Step 2: strips a zero-width char introduced elsewhere in the text.
    step1 = SpanMap.identity(5).compose([Edit(Span(0, 1), Span(0, 1))])
    step2 = step1.compose([Edit(Span(3, 4), Span(3, 3))])

    # raw "d" (originally raw index 4, after step1 unchanged) now sits at
    # normalized index 3 after step2 removed the char before it.
    assert step2.to_raw(Span(3, 4)) == Span(4, 5)
    assert step2.to_normalized(Span(4, 5)) == Span(3, 4)


def test_to_normalized_returns_none_outside_mapped_raw_range():
    span_map = SpanMap.identity(3)
    assert span_map.to_normalized(Span(10, 12)) is None


def test_to_normalized_maps_deleted_raw_range_to_empty_span():
    span_map = SpanMap.identity(5).compose([Edit(Span(2, 3), Span(2, 2))])
    assert span_map.to_normalized(Span(2, 3)) == Span(2, 2)
