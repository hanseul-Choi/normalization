# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-09-17

First official production release of **secnorm**: a deterministic, audit-friendly text normalization and security analysis engine for LLM inputs and security filters.

### Key Highlights
- **7-Stage Normalization Pipeline**: Fully deterministic text normalization with audit trailing and full character-level span mapping (`SpanMap`).
- **5 Built-in Presets**: Tailored for various operational needs (`minimal`, `nlp_preprocessing`, `security_balanced`, `security_strict`, `llm_input_sanitize`).
- **Consolidated Risk Scoring**: Multi-vector threat scoring engine (`RiskScorer`, `RiskReport`) calculating risk scores (0.0–1.0), risk levels (`clean`, `low`, `medium`, `high`, `critical`), and recommended actions (`allow`, `flag`, `block`).
- **High-Precision CJK Detection**: Script-ratio analysis combined with Kanji/Hanzi marker dictionaries (`JAPANESE_SPECIFIC_HAN`, `SIMPLIFIED_CHINESE_SPECIFIC_HAN`) for offline Japanese/Chinese disambiguation.
- **Microservice & Streaming Ready**: Generator-based streaming (`normalize_stream`), file line-by-line conversion (`normalize_file`), and built-in HTTP REST API daemon (`secnorm serve`).
- **Zero Heavy ML Dependencies**: Pure Python implementation with minimal optional dependencies for ultra-fast, predictable CPU execution.

### Added
- **Core Pipeline & Data Models** (`Phase 0`, `Phase 1`):
  - `NormalizationResult`, `Transformation`, `SuspicionFlag`, `LanguageMetadata`, `StructuralHints`.
  - Precise piecewise-linear `SpanMap` and `Edit` tracking across all pipeline transformations.
  - Step 1: Unicode normalization (`NFC`, `NFD`, `NFKC`, `NFKD`).
  - Step 2: Invisible and control character sanitization (bidi override, tag characters, zero-width spaces, hangul fillers, unassigned code points).
  - Step 3: Whitespace normalization (strict single space collapsing or structural markdown/code preserving).
  - Step 4: Encoding & escape decoding (HTML entities, URL percent-encoding, `\uXXXX` escape sequences, mojibake repair).
  - Serialization support via `to_dict()`, `to_json()`, `from_json()`, and `from_file()`.
- **Heuristics & Language Metadata** (`Phase 2`):
  - Step 5: Repetition cap normalization with category-aware thresholds and grapheme cluster awareness.
  - Step 7: Language detection (hybrid rule-based script ratio + `langdetect` fallback) and structural detection (HTML, Markdown, URL, Email, Code blocks).
  - Standalone `compute_script_ratios` prepass interface.
- **Adversarial Obfuscation Normalization** (`Phase 3`):
  - Bundled UTS #39 Confusables mapping (Unicode 16.0.0).
  - Step 6 Homoglyph canonical normalization.
  - Separator injection detection and aggressive variant generation.
  - Leetspeak symbol substitution normalization into `normalized_variants["aggressive"]`.
  - Base64 / Hex encoded payload detection and recursive sanitization.
- **Custom Extensibility & Quality Infrastructure** (`Phase 4`):
  - Plugin architecture: `insert_step(..., after=..., before=...)`, `replace_step()`, `enable()`, `disable()`.
  - Property-based testing suite with Hypothesis (ASCII idempotency, Unicode totality, crash resistance).
  - Benchmark performance suite measuring sub-millisecond latencies across presets.
  - CLI commands with `--preset`, `--json`, and `--no-raw` support.
- **CI/CD & Packaging** (`Phase 5`):
  - Matrix testing across Python 3.10, 3.11, 3.12, 3.13.
  - Type annotations and `py.typed` compliance verification.
- **Streaming & File Tools** (`Phase 6`):
  - Memory-efficient streaming API: `normalize_stream(iterable)`.
  - Batch file translation API: `normalize_file(input_path, output_path, format="text"|"jsonl")`.
  - Automated Confusables updater script: `scripts/build_confusables.py`.
- **Guardrail Plugins & HTTP Daemon** (`Phase 7`):
  - `KeywordMatcherStep` powered by pure-Python Trie.
  - `RegexGuardrailStep` for configurable pattern-based input gating.
  - Zero-dependency HTTP daemon via `secnorm.server` and `secnorm serve`.
- **Risk Scoring Engine** (`Phase 8`):
  - Multi-factor risk calculation with severity weights and cross-vector synergy boosts.
  - Integrated directly via `result.evaluate_risk()` and CLI `--score`.
- **CJK Refinement & Extended Scripts** (`Phase 9`):
  - Dictionaries for Japanese Kokuji/Shinjitai and Simplified Hanzi.
  - Extended script ratio detection: Cyrillic, Greek, Arabic.
- **Release Automation** (`Phase 10`):
  - Version bump to 1.0.0.
  - Automated PyPI & GitHub Releases workflow (`.github/workflows/publish.yml`).
  - Packaging validation and version integrity test suite.
