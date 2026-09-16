# 01. 개요 (Overview)

## 프로젝트

- 잠정 패키지명: **`textnorm`** (확정 아님, `10-api-design.md` 참고)
- 형태: `pip install` 가능한 순수 CPU 기반 Python 라이브러리 (`import textnorm`)
- 언어: Python 3.10+

## 문제 정의

사용자 입력 텍스트(채팅, 댓글, 프롬프트 등)는 다음과 같은 이유로 "보이는 그대로"가 아닐 수 있다.

- 유니코드에는 시각적으로 동일하거나 유사하게 보이는 문자가 여러 개 존재한다 (전각/반각, 호환 문자, homoglyph 등).
- 눈에 보이지 않는 제어/포맷 문자(zero-width space, bidi override, Unicode Tag 문자 등)를 이용해 필터를 우회하거나 사람이 인지하지 못하는 내용을 텍스트에 숨길 수 있다.
- 공백, 반복 문자, 인코딩(HTML entity, URL encoding, unicode escape) 등을 조작해 문자열 매칭 기반 필터를 우회할 수 있다.
- 의도적인 난독화(leetspeak, 문자 사이 구분자 삽입, base64/hex 페이로드 은닉)로 금칙어·패턴 탐지를 회피할 수 있다.

이런 다양한 변형을 **하나의 정규화된 표준 뷰(Normalized View)** 로 수렴시켜서, 이후 단계(스팸/우회 탐지, LLM 프롬프트 필터링, 검색/분류 등)가 "정규화된 텍스트 한 벌"만 보고 일관되게 판단할 수 있게 하는 것이 이 라이브러리의 목적이다.

## 주 사용 시나리오 (확정됨)

1. **보안/우회 탐지 (1순위)** — 스팸, 콘텐츠 모더레이션 우회, 프롬프트 인젝션/탈옥 시도 등 "의도적으로 난독화된 텍스트"를 표준화하고, 어떤 우회 기법이 사용됐는지 감사(audit) 가능한 형태로 남긴다.
2. **LLM 입력 정제** — 위와 밀접하게 연결. Unicode Tag 문자·bidi override·variation selector를 이용한 "ASCII smuggling" 류의 최신 공격 벡터도 이 파이프라인이 커버 범위에 포함한다 (`04-step2-invisible-control-chars.md` 참고).
3. 실행 모드는 **실시간 단건 메시지 처리**가 기준 시나리오다 (배치/대용량 처리량 최적화는 1순위가 아님). 따라서 API는 지연시간(latency)을 우선하는 동기 함수 호출 형태를 기본으로 하고, 배치 처리는 이를 감싸는 얇은 래퍼로 제공한다.

## 지원 언어/스크립트 (v1)

한국어(Hangul), 영어(Latin), 일본어(Hiragana/Katakana/Kanji), 중국어(Hanzi) — 이 4개 언어/스크립트를 1차 지원 범위로 한다. 다른 언어(아랍어, 태국어 등)는 구조적으로 확장 가능하게 설계하되 v1 구현/튜닝 대상에서는 제외한다.

## 출력 형태 (확정됨)

단순 정규화 문자열이 아니라, **리치 감사 객체(`NormalizationResult`)** 를 반환한다.

- 정규화된 텍스트
- 각 파이프라인 단계에서 적용된 변환 내역 (`Transformation` 목록)
- 의심스러운 패턴에 대한 플래그 (`SuspicionFlag` 목록) — 탐지만 하고 점수/판정은 내리지 않음 (스코어링/분류는 이 라이브러리의 책임이 아니라 상위 레이어의 책임)
- 언어/구조 메타데이터
- 정규화 텍스트 ↔ 원본 텍스트 간 위치(span) 매핑 — 원본에서 어느 부분이 왜 바뀌었는지 하이라이트할 수 있어야 함

자세한 데이터 모델은 `02-architecture.md` 참고.

## 설계 원칙

1. **결정적(deterministic)이고 감사 가능해야 한다.** 같은 입력 + 같은 설정 + 같은 규칙 버전이면 항상 같은 출력. 규칙(confusables 테이블 등)이 바뀌면 `pipeline_version`/데이터 버전을 함께 기록한다.
2. **보수적 기본값(conservative by default).** 정상 텍스트를 오염시키는 것(false positive로 인한 파괴적 변환)이, 우회 패턴을 한 번 더 놓치는 것보다 나쁘다. 특히 6단계(난독화 정규화)는 공격적인 규칙일수록 "정규 텍스트를 별도 후보로만 제공"하고 canonical `normalized_text`는 훼손하지 않는 전략을 취한다 (`08-step6-obfuscation-normalization.md` 참고).
3. **각 단계는 켜고 끌 수 있고, 순서를 바꾸거나 커스텀 단계를 끼울 수 있어야 한다.** (확정됨 — `02-architecture.md`)
4. **순수 CPU, 가벼운 의존성.** 무거운 ML/딥러닝 모델(언어감지용 transformer 등)은 쓰지 않는다. 표준 라이브러리를 우선하고, 필요한 경우에만 가벼운 서드파티 패키지를 허용한다 (`11-dependencies.md`).
5. **성능은 단건 지연시간 기준.** 평균적인 길이의 메시지(예: 수백 자)를 한 자리 밀리초~수 밀리초 내에 처리하는 것을 목표로 한다 (`12-testing-strategy.md`의 벤치마크 항목).

## 파이프라인 개요

```
Raw Input
   ↓
1. Unicode normalization
   ↓
2. Invisible/control character handling
   ↓
3. Whitespace normalization
   ↓
4. Encoding / escaping normalization
   ↓
5. Repeated-character normalization
   ↓
6. Optional obfuscation normalization
   ↓
7. Language / structural metadata extraction
   ↓
Normalized View (NormalizationResult)
```

각 단계의 상세 설계는 `03`~`09` 문서를, 전체 아키텍처(데이터 모델/확장 구조)는 `02-architecture.md`를 참고.

## 문서 목차

| 문서 | 내용 |
|---|---|
| [02-architecture.md](./02-architecture.md) | 데이터 모델, 파이프라인 실행 모델, span mapping, 확장 구조 |
| [03-step1-unicode-normalization.md](./03-step1-unicode-normalization.md) | 1단계: Unicode 정규화 |
| [04-step2-invisible-control-chars.md](./04-step2-invisible-control-chars.md) | 2단계: 비가시/제어 문자 처리 |
| [05-step3-whitespace-normalization.md](./05-step3-whitespace-normalization.md) | 3단계: 공백 정규화 |
| [06-step4-encoding-escaping.md](./06-step4-encoding-escaping.md) | 4단계: 인코딩/이스케이프 정규화 |
| [07-step5-repeated-characters.md](./07-step5-repeated-characters.md) | 5단계: 반복 문자 정규화 |
| [08-step6-obfuscation-normalization.md](./08-step6-obfuscation-normalization.md) | 6단계: 난독화 정규화 (optional) |
| [09-step7-language-structural-metadata.md](./09-step7-language-structural-metadata.md) | 7단계: 언어/구조 메타데이터 추출 |
| [10-api-design.md](./10-api-design.md) | 공개 API, 설정, 프리셋 |
| [11-dependencies.md](./11-dependencies.md) | 의존성 정책과 단계별 선택 라이브러리 |
| [12-testing-strategy.md](./12-testing-strategy.md) | 테스트/평가 전략 |
| [13-roadmap.md](./13-roadmap.md) | 구현 단계(phase)와 범위 |
