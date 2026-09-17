"""Span mapping between raw_text and the text produced by each pipeline step.

Implements the composition algorithm described in `docs/02-architecture.md`
("Span Mapping"): unchanged regions are kept as an identity mapping, changed
regions are collapsed to the edit's `src_span` as a single blob (no
character-level diffing, since each step already produces minimal edits).
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Span


@dataclass(slots=True, frozen=True)
class Edit:
    src_span: Span
    dst_span: Span


@dataclass(slots=True, frozen=True)
class _Segment:
    # cur_span is expressed in the coordinates of the text this SpanMap
    # currently maps *to* (i.e. the latest pipeline stage's output).
    cur_span: Span
    raw_span: Span
    # exact=True means the mapping from raw_span to cur_span is a plain
    # offset (1:1, nothing was ever inserted/deleted/collapsed along the
    # chain), so sub-ranges can be sliced precisely. exact=False means this
    # segment descends from at least one edit, so any sub-range query
    # collapses to the whole raw_span/cur_span (blobbed).
    exact: bool


def _overlaps(a: Span, b: Span) -> bool:
    return a.start < b.end and b.start < a.end


def _envelope(spans: list[Span]) -> Span:
    return Span(min(s.start for s in spans), max(s.end for s in spans))


class SpanMap:
    def __init__(self, segments: list[_Segment]) -> None:
        self._segments = segments

    @classmethod
    def identity(cls, length: int) -> "SpanMap":
        span = Span(0, length)
        return cls([_Segment(span, span, True)])

    @property
    def _cur_length(self) -> int:
        return self._segments[-1].cur_span.end if self._segments else 0

    def _segments_overlapping_cur(self, span: Span) -> list[_Segment]:
        return [seg for seg in self._segments if _overlaps(seg.cur_span, span)]

    def _segments_overlapping_raw(self, span: Span) -> list[_Segment]:
        return [seg for seg in self._segments if _overlaps(seg.raw_span, span)]

    def _point_to_raw(self, pos: int) -> int:
        for seg in self._segments:
            if seg.cur_span.start <= pos < seg.cur_span.end:
                if seg.exact:
                    return seg.raw_span.start + (pos - seg.cur_span.start)
                return seg.raw_span.start
        if self._segments and pos >= self._segments[-1].cur_span.end:
            return self._segments[-1].raw_span.end
        return 0

    def _slice_raw(self, seg: _Segment, overlap: Span) -> Span:
        if seg.exact:
            offset_start = overlap.start - seg.cur_span.start
            offset_end = overlap.end - seg.cur_span.start
            return Span(seg.raw_span.start + offset_start, seg.raw_span.start + offset_end)
        return seg.raw_span

    def _slice_cur(self, seg: _Segment, overlap: Span) -> Span:
        if seg.exact:
            offset_start = overlap.start - seg.raw_span.start
            offset_end = overlap.end - seg.raw_span.start
            return Span(seg.cur_span.start + offset_start, seg.cur_span.start + offset_end)
        return seg.cur_span

    def to_raw(self, normalized_span: Span) -> Span:
        overlapping = self._segments_overlapping_cur(normalized_span)
        if not overlapping:
            point = self._point_to_raw(normalized_span.start)
            return Span(point, point)
        pieces = [
            self._slice_raw(seg, Span(max(seg.cur_span.start, normalized_span.start), min(seg.cur_span.end, normalized_span.end)))
            for seg in overlapping
        ]
        return _envelope(pieces)

    def to_normalized(self, raw_span: Span) -> Span | None:
        overlapping = self._segments_overlapping_raw(raw_span)
        if not overlapping:
            return None
        pieces = [
            self._slice_cur(seg, Span(max(seg.raw_span.start, raw_span.start), min(seg.raw_span.end, raw_span.end)))
            for seg in overlapping
        ]
        return _envelope(pieces)

    def _pieces_for_old_range(self, start: int, end: int) -> list[tuple[Span, Span, bool]]:
        pieces: list[tuple[Span, Span, bool]] = []
        query = Span(start, end)
        for seg in self._segments:
            if not _overlaps(seg.cur_span, query):
                continue
            overlap = Span(max(start, seg.cur_span.start), min(end, seg.cur_span.end))
            if overlap.start >= overlap.end:
                continue
            pieces.append((overlap, self._slice_raw(seg, overlap), seg.exact))
        return pieces

    def compose(self, edits: list[Edit]) -> "SpanMap":
        """Fold this step's edits (in old-stage coordinates) into a new SpanMap.

        `edits` describe, for the step that just ran, which old-stage ranges
        (`src_span`) turned into which new-stage ranges (`dst_span`). Ranges
        not covered by any edit are assumed unchanged (identity, shifted by
        the cumulative length delta of preceding edits).
        """
        old_length = self._cur_length
        sorted_edits = sorted(edits, key=lambda e: e.src_span.start)

        new_segments: list[_Segment] = []
        cur_pos = 0
        new_pos = 0

        def emit_gap(gap_start: int, gap_end: int) -> None:
            nonlocal new_pos
            if gap_end <= gap_start:
                return
            shift = new_pos - gap_start
            for piece_cur, piece_raw, exact in self._pieces_for_old_range(gap_start, gap_end):
                new_cur = Span(piece_cur.start + shift, piece_cur.end + shift)
                new_segments.append(_Segment(new_cur, piece_raw, exact))
            new_pos += gap_end - gap_start

        for edit in sorted_edits:
            emit_gap(cur_pos, edit.src_span.start)
            cur_pos = edit.src_span.start

            pieces = self._pieces_for_old_range(edit.src_span.start, edit.src_span.end)
            if pieces:
                raw_span = _envelope([raw for _, raw, _ in pieces])
            else:
                anchor = self._point_to_raw(edit.src_span.start)
                raw_span = Span(anchor, anchor)
            is_noop = edit.src_span.start == edit.src_span.end and edit.dst_span.start == edit.dst_span.end
            if not is_noop:
                new_segments.append(_Segment(edit.dst_span, raw_span, False))

            cur_pos = edit.src_span.end
            new_pos = edit.dst_span.end

        emit_gap(cur_pos, old_length)

        if not new_segments:
            span = Span(0, 0)
            new_segments.append(_Segment(span, span, True))

        return SpanMap(new_segments)
