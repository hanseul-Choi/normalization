# 13. 로드맵

## Phase 0 — 프로젝트 뼈대

- 패키지명 확정 (PyPI 충돌 확인), `pyproject.toml`, 패키지 레이아웃 구성
- 핵심 데이터 모델 구현 (`Transformation`, `SuspicionFlag`, `LanguageMetadata`, `NormalizationResult`, `Span`/`Edit`/`SpanMap`) — `02-architecture.md`
- `PipelineStep` 프로토콜, `NormalizationPipeline`, `NormalizationConfig` 뼈대
- Span mapping 합성 알고리즘 구현 + 유닛 테스트

## Phase 1 — "안전한" 결정적 단계 (1~4단계) [완료]

우회 탐지 특화 로직 없이도 그 자체로 유용하고, 구현 리스크가 낮은 단계부터.

- 1단계 Unicode normalization (NFC/NFD/NFKC/NFKD, unicodedata2 우선 사용 폴백)
- 2단계 비가시/제어 문자 처리 (Tag 문자/bidi override/VS/zero-width/Hangul filler/PUA/미할당 처리)
- 3단계 공백 정규화 (strict/structural 모드, 전각 공백 및 탭 정책)
- 4단계 인코딩/이스케이프 정규화 (HTML entity, URL percent-encoding, unicode escape, ftfy mojibake 복구)
- `security_balanced`(1~4단계 축소 버전)/`minimal` 프리셋 및 최상위 `secnorm.normalize()`, `secnorm.normalize_batch()`, `Pipeline` API
- 결과 및 설정 직렬화 (`to_dict`, `to_json`, `from_json`, `from_file`), `py.typed` 마커, `hypothesis` 속성 기반 테스트 포함

## Phase 2 — 통계/휴리스틱 단계 (5, 7단계) [완료]

- 5단계 반복 문자 정규화 (카테고리별 cap: 일반문자 2, 한글자모/구두점/이모지 3, grapheme cluster/conjoining jamo 지원, 5회 이상 반복 시 excessive_repetition 플래그)
- 7단계 스크립트 비율 계산 + 하이브리드 언어 판별(1차 스크립트 규칙, 2차 langdetect 폴백) + 구조 메타데이터(HTML, Markdown, URL, Email, Code block, 문장/단어 수, LTR)
- 6단계가 필요로 하는 standalone "script ratio prepass" 인터페이스 (`compute_script_ratios`) 확정
- `nlp_preprocessing` 프리셋(1~5단계, 7단계 on, structural 공백 모드) 및 `security_balanced` 프리셋의 5·7단계 통합 완료

## Phase 3 — 난독화 정규화 (6단계, 가장 리스크 높음) [완료]

- Confusables 데이터 구축 (`secnorm.data.confusables`, UTS #39 Confusables 16.0.0 기반 대소문자 매핑 테이블 번들링)
- Homoglyph 정규화 (단일 스크립트 외래어 보존 예외 처리, canonical 반영, `homoglyph` 플래그)
- 구분자 삽입 탐지 (canonical 보존, `normalized_variants["aggressive"]` 반영, `separator_injection` 플래그)
- Leetspeak 정규화 (`normalized_variants["aggressive"]` 반영, 3개 이상 치환 시 `leetspeak` 플래그)
- 인코딩된 페이로드 탐지 (Base64/Hex 탐지, `encoded_payload` 플래그, `decode_and_recurse=True` 안전장치 포함 재귀 정규화)
- 5종 프리셋 완성 (`minimal`, `nlp_preprocessing`, `security_balanced`, `security_strict`, `llm_input_sanitize`)
- 적대적 테스트 코퍼스 및 유닛/통합 테스트 구축 (총 108개 테스트 통과)

## Phase 4 — 통합/품질 [완료]

- 프리셋 5종 확정 및 튜닝 (`minimal`, `nlp_preprocessing`, `security_balanced`, `security_strict`, `llm_input_sanitize`)
- 커스텀 단계 플러그인 API 안정화 (`insert_step(..., after=..., before=..., enabled=...)`, `replace_step(...)`, `steps` 프로퍼티)
- Property-based 테스트 보강 (ASCII 비파괴성, 임의 유니코드 총함수(Total function) 속성, DoS 내성 검증)
- 벤치마크 테스트 스위트 구축 (`pytest-benchmark`, 30자/200자/2000자 구간별 5개 프리셋 지연시간 측정)
- CLI 구현 (`secnorm` 콘솔 스크립트 및 `python -m secnorm`, `--preset`, `--json`, `--no-raw` 지원)
- 문서화 완성 (README 가이드, 사용 예제, `py.typed` 및 docstring 보강)

## Phase 5 — CI/CD 자동화, 배포 준비 및 예제 [완료]

- GitHub Actions CI 워크플로우 구성 (`.github/workflows/ci.yml`): 멀티 Python 버전(3.10~3.13) 테스트, 벤치마크, 빌드 검증
- 실무 예제 스크립트 구축 (`examples/demo_adversarial_inspection.py`, `examples/demo_custom_step.py`, `examples/demo_batch_processing.py`)
- sdist / wheel 빌드 및 `py.typed` 패키징 무결성 검증 완료

## Phase 6 — 스트리밍 처리, 파일 I/O 및 빌드 도구 [완료]

- 제너레이터 기반 대용량 스트리밍 정규화 API (`secnorm.normalize_stream`)
- 파일 단위 스트리밍 변환 및 JSONL 지원 (`secnorm.normalize_file`)
- CLI 파일 입출력 플래그 (`-i/--input`, `-o/--output`, `--format text|jsonl`)
- UTS #39 Confusables 데이터 빌드 및 자동 갱신 스크립트 (`scripts/build_confusables.py`)

## Phase 7 — 가드레일 플러그인 팩 및 HTTP API 데몬 [완료]

- 외부 주입 사전 고속 매칭 플러그인 (`secnorm.plugins.KeywordMatcherStep`, 순수 파이썬 Trie 지원)
- 보안 정규식 탐지 가드레일 플러그인 (`secnorm.plugins.RegexGuardrailStep`)
- 표준 라이브러리 기반 경량 HTTP REST API 서버 데몬 (`secnorm.server` / `secnorm serve`)
- 마이크로서비스 연동 테스트 및 CLI 서브커맨드 구현 완료

## v1 범위 밖 (명시적 제외, 향후 후보)

- 스트리밍/대용량 배치 처리량 최적화 (병렬 워커, 청크 스트리밍) — v1은 실시간 단건 처리가 우선
- ko/en/ja/zh 외 언어 지원 확장
- ML 기반 스코어링/분류 (이 라이브러리는 신호 추출까지만 담당, 판정은 상위 레이어 책임)
- 내장 금칙어/블록리스트 사전 (외부 주입 방식 유지)
- CLI 고도화, 웹 서비스/데몬화

## 열린 질문 (구현 중 재확인 필요)

- confusables 데이터 갱신 주기 및 자동화 여부 (수동 vs CI 스케줄)
- `langdetect`의 ja/zh 폴백 정확도가 실제 데이터에서 충분한지 (부족하면 Phase 2에서 대안 재검토)
