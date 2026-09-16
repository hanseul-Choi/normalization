# 12. 테스트/평가 전략

## 1. 단계별 유닛 테스트 (골든 케이스)

각 단계 문서(`03`~`09`)의 "예시" 표를 그대로 테스트 픽스처의 출발점으로 삼는다. 형식:

```python
# tests/fixtures/step1_unicode.yaml
- input: "Ａｄｍｉｎ"
  expected_output: "Admin"
  expected_transformations: ["unicode.normalize_NFKC"]
- input: "① ② ③"
  expected_output: "1 2 3"
```

YAML/JSON 픽스처로 관리해서, 코드 변경 없이 케이스를 추가할 수 있게 한다. 각 단계는 독립적으로(파이프라인 전체를 안 돌리고) 단위 테스트 가능해야 한다 — `PipelineStep.apply()`를 직접 호출하는 테스트.

## 2. 파이프라인 통합 테스트

여러 단계가 상호작용하는 케이스 (예: 4단계에서 디코딩된 결과가 5단계 반복문자 축약 대상이 되는 경우, 6단계 homoglyph가 7단계 언어감지 이전 prepass와 맞물리는 경우)를 별도로 검증.

## 3. 적대적(adversarial) 테스트 코퍼스

**목적**: 실제 알려진 우회/난독화 기법들이 정규화 후 올바르게 탐지/처리되는지 검증. 이 코퍼스는 방어 목적(defensive)으로만 구축·사용하며, 공개된 보안 연구 자료(Unicode Technical Report #36/#39, 공개된 유니코드 스푸핑/프롬프트 인젝션 연구 등)에서 케이스를 인용한다.

포함 카테고리:
- Homoglyph 도메인/단어 스푸핑 샘플 (`аpple.com` 류)
- Zero-width 문자 스테가노그래피 샘플
- Bidi override를 이용한 "Trojan Source" 패턴
- Unicode Tag 문자 기반 프롬프트 인젝션 PoC
- Leetspeak/구분자 삽입 스팸 샘플
- 반복 문자 도배 샘플

각 샘플에 대해 "정규화 후 flags에 기대하는 category/severity가 포함되는가"를 검증 (정확히 어떤 텍스트로 바뀌는지보다, 올바른 신호가 뜨는지가 더 중요한 케이스가 많음).

## 4. Property-based 테스트 (`hypothesis`)

- **멱등성(idempotency)**: `normalize(normalize(x).normalized_text) == normalize(x).normalized_text` — 이미 정규화된 텍스트를 다시 넣으면 추가 변화가 없어야 함. 정규화 파이프라인의 핵심 불변식.
- **Span map 왕복 일관성**: 임의의 정규화 결과에 대해, `normalized_text`의 임의 span을 `span_map.to_raw()`로 변환했을 때 유효한 `raw_text` 범위 안에 있어야 하고, 역변환이 일관되어야 함.
- **비파괴성(non-corruption, `minimal`/`nlp_preprocessing` 프리셋 한정)**: 순수 ASCII 정상 영문 텍스트 무작위 생성 시, 원본과 정규화 결과가 (공백/trim 제외) 의미상 동일해야 함 — 공격적 프리셋에서 정상 텍스트를 과도하게 건드리지 않는지 회귀 감지.
- **DoS 내성**: 임의의 긴 반복 입력, 깊게 중첩된 인코딩 패턴 등에 대해 처리 시간이 입력 길이에 선형적으로 유지되는지 (ReDoS 회귀 감지).

## 5. 벤치마크 (지연시간 중심 — 확정된 실시간 단건 처리 시나리오 반영)

- 대표 길이 구간별(30자/200자/2000자) p50/p95/p99 지연시간 측정.
- 프리셋별(minimal ~ security_strict) 비교 — 6단계 on/off의 비용 차이를 명시적으로 추적.
- CI에 벤치마크 회귀 감지 포함 (예: 이전 대비 20% 이상 느려지면 실패) — `pytest-benchmark` 사용 고려.

## 6. 규칙 데이터 변경 시 회귀 테스트

confusables 데이터, 이모지 데이터 등이 업데이트될 때 `rule_data_version`이 올바르게 올라가는지, 기존 골든 케이스가 깨지지 않는지 별도 CI job으로 검증.

## 도구

- `pytest` + `pytest-benchmark` + `hypothesis`. 전부 순수 Python 테스트 도구, 프로덕션 의존성에는 포함되지 않음 (`dev` extra로 분리).
