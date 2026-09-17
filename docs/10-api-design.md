# 10. API 설계

## 패키지명

`secnorm` (PyPI 미등록 확인 완료, `13-roadmap.md` Phase 0 항목).

## 최상위 함수형 API (가장 흔한 사용 패턴)

```python
import secnorm

result = secnorm.normalize(text)          # 기본 프리셋: "security_balanced"
result.normalized_text
result.flags                                # list[SuspicionFlag]
result.language.primary_language
result.transformations
```

```python
result = secnorm.normalize(text, preset="security_strict")
```

## 프리셋 (확정 설계)

| 프리셋 | 용도 | 특징 |
|---|---|---|
| `security_strict` | 스팸/우회 탐지 최우선, 오탐 감수 | 6단계 전체 on + `decode_and_recurse` on |
| `security_balanced` (기본) | 실서비스 실시간 처리 기본값 | homoglyph만 canonical 반영, 나머지 6단계는 탐지(플래그)만 |
| `llm_input_sanitize` | LLM에 넣기 전 정제 | 2단계(invisible/control, 특히 tag char/bidi/VS)를 최우선 강화, 나머지는 `security_balanced`와 유사 |
| `nlp_preprocessing` | 검색/분류 등 일반 NLP | 1~5단계만, 6단계 off, `whitespace.mode="structural"` |
| `minimal` | 최소 정규화만 | 1단계(unicode NFC)와 3단계 공백 trim만 |

## Pipeline 객체 (세밀 제어)

```python
pipeline = secnorm.Pipeline.from_preset("security_balanced")
pipeline.disable("obfuscation")
pipeline.config.repeated_char.default_cap = 3

result = pipeline.run(text)
```

## 커스텀 단계 추가 (확정됨: 플러그인 지원)

```python
class ProfanityMaskStep:
    name = "profanity_mask"

    def apply(self, ctx: secnorm.PipelineContext) -> secnorm.StepOutput:
        ...

pipeline.insert_step(ProfanityMaskStep(), after="obfuscation")
```

## 배치 처리 (2차 우선순위 — 얇은 래퍼)

```python
results = secnorm.normalize_batch(texts, preset="security_balanced", n_jobs=4)
```

내부적으로 `concurrent.futures.ProcessPoolExecutor` 또는 `ThreadPoolExecutor` 기반 (CPU 바운드 작업이므로 프로세스 풀이 기본, GIL 영향이 큰 경우). v1에서는 단건 API의 얇은 반복 래퍼로 시작하고, 실제 처리량 요구가 생기면 `13-roadmap.md`의 향후 단계에서 스트리밍/병렬화를 본격 설계.

## 설정 직렬화

```python
config = secnorm.NormalizationConfig.from_json(json_str)
config = secnorm.NormalizationConfig.from_file("config.toml")
pipeline = secnorm.Pipeline(config=config)
```

`json` / `tomllib`(3.11+, 3.10은 `tomli` 폴백) 표준 라이브러리 사용.

## 결과 객체 직렬화 (로깅/감사용)

```python
result.to_dict()   # JSON-직렬화 가능한 dict
result.to_json()
```

민감정보(원본 텍스트) 포함 여부를 제어하는 `include_raw_text: bool = True` 파라미터 제공 — 감사 로그 저장 정책에 따라 원본을 뺄 수 있어야 함.

## CLI (v1 범위 밖, 향후 고려)

`13-roadmap.md` Phase 4 이후 항목으로 `python -m secnorm "text"` 형태의 간단한 CLI만 우선 고려. 본 라이브러리의 핵심 가치는 라이브러리 API이므로 CLI는 부가 기능.

## 타입 힌트 / 정적 검사

- 전체 public API에 타입 힌트 필수, `py.typed` 마커 포함해 배포 (PEP 561) — 이 라이브러리를 import하는 쪽에서도 타입 체크 혜택.
