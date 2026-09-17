"""Unit tests for secnorm.plugins pack (Trie, KeywordMatcherStep, RegexGuardrailStep)."""

import pytest
import secnorm
from secnorm.models import Span
from secnorm.plugins import KeywordMatcherStep, RegexGuardrailStep, Trie


def test_trie_multi_keyword_matching():
    trie = Trie(["apple", "banana", "orange", "app"])
    text = "I love apple and banana"
    matches = trie.find_all(text)
    # Both "app" and "apple" match at start 7
    matched_words = [m[2] for m in matches]
    assert "apple" in matched_words
    assert "app" in matched_words
    assert "banana" in matched_words


def test_trie_case_insensitive():
    trie = Trie(["secret", "confidential"])
    text = "This is SECRET and Confidential"
    matches = trie.find_all(text, case_sensitive=False)
    assert len(matches) == 2
    words = [m[2] for m in matches]
    assert words == ["secret", "confidential"]


def test_keyword_matcher_detection_in_pipeline():
    pipeline = secnorm.Pipeline.from_preset("security_balanced")
    step = KeywordMatcherStep(["forbidden", "malware"])
    pipeline.insert_step(step, after="obfuscation")

    res = pipeline.run("Notice: this forbidden file is safe.")
    assert any(f.category == "keyword_match" for f in res.flags)
    match_flag = next(f for f in res.flags if f.category == "keyword_match")
    assert "forbidden" in match_flag.detail

    # Verify flag coordinates map accurately to raw text
    start, end = match_flag.span.start, match_flag.span.end
    assert res.raw_text[start:end] == "forbidden"


def test_keyword_matcher_with_masking():
    pipeline = secnorm.Pipeline.from_preset("minimal")
    step = KeywordMatcherStep(["badword"], mask="***")
    pipeline.insert_step(step, after="whitespace")

    res = pipeline.run("Eliminate this badword right now.")
    assert res.normalized_text == "Eliminate this *** right now."
    assert any(t.rule == "mask_keyword" for t in res.transformations)

    # Check SpanMap roundtrip across masking
    mask_start = res.normalized_text.index("***")
    raw_span = res.span_map.to_raw(Span(mask_start, mask_start + 3))
    assert res.raw_text[raw_span.start:raw_span.end] == "badword"


def test_regex_guardrail_detection():
    patterns = {
        "api_key": r"sk-[a-zA-Z0-9]{12}",
        "phone": r"\b\d{3}-\d{4}-\d{4}\b",
    }
    step = RegexGuardrailStep(patterns, severity="high")
    pipeline = secnorm.Pipeline.from_preset("security_balanced")
    pipeline.insert_step(step, after="obfuscation")

    text = "Contact 010-1234-5678 with key sk-abcdef123456."
    res = pipeline.run(text)

    regex_flags = [f for f in res.flags if f.category.startswith("regex_")]
    assert len(regex_flags) == 2
    categories = {f.category for f in regex_flags}
    assert categories == {"regex_api_key", "regex_phone"}


def test_regex_guardrail_masking():
    patterns = {
        "secret_code": r"\bSECRET-\d+\b",
    }
    step = RegexGuardrailStep(patterns, mask="[REDACTED]")
    pipeline = secnorm.Pipeline.from_preset("minimal")
    pipeline.insert_step(step, after="whitespace")

    res = pipeline.run("Token is SECRET-9999 for access.")
    assert res.normalized_text == "Token is [REDACTED] for access."
    assert any(t.rule == "mask_secret_code" for t in res.transformations)
