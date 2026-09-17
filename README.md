# secnorm

의도적으로 난독화되거나 변형된 텍스트를 **표준화된 정규화 뷰(Normalized View)** 로 수렴시키는 CPU 기반 Python 라이브러리 기획.

## 왜 필요한가

유니코드 텍스트는 "보이는 그대로"가 아닐 수 있다. 전각/반각 문자, 눈에 안 보이는 제어 문자, homoglyph(시각적으로 동일한 다른 스크립트 문자), leetspeak, 반복 문자 도배, HTML/URL 인코딩 등을 이용해 문자열 매칭 기반 필터를 우회하거나, 사람 눈에는 안 보이지만 시스템(특히 LLM)에는 읽히는 내용을 텍스트에 숨길 수 있다.

이 라이브러리는 그런 다양한 변형을 하나의 정규화된 표준 형태로 수렴시켜서, 이후 단계(스팸/콘텐츠 모더레이션 우회 탐지, LLM 프롬프트 정제, 검색/분류 등)가 일관된 기준으로 판단할 수 있게 한다.

## 주 용도

1. **보안/우회 탐지** (1순위) — 스팸, 콘텐츠 모더레이션 우회, 프롬프트 인젝션/탈옥 시도 등에 쓰인 난독화 기법을 표준화하고 감사 가능한 형태로 기록
2. **LLM 입력 정제** — Unicode Tag 문자, bidi override, variation selector를 이용한 "ASCII smuggling"류 최신 공격 벡터 포함 대응
3. 실행 모드는 **실시간 단건 메시지 처리**를 기준으로 설계 (배치는 2차 우선순위)

## 지원 언어/스크립트 (v1)

한국어(Hangul), 영어(Latin), 일본어(Hiragana/Katakana/Kanji), 중국어(Hanzi)

## 파이프라인

```
Raw Input
   ↓
1. Unicode normalization              — NFKC로 전각/호환 문자 등을 표준 형태로 수렴
   ↓
2. Invisible/control character handling — zero-width, bidi override, Unicode Tag 문자(프롬프트 스머글링) 등 제거/플래그
   ↓
3. Whitespace normalization           — 각종 폭의 공백류 문자를 표준 공백으로
   ↓
4. Encoding / escaping normalization  — HTML entity, URL encoding, unicode escape 디코딩 (mojibake 복구는 선택)
   ↓
5. Repeated-character normalization   — 카테고리별 상한으로 반복 문자 축약, 원본 반복 횟수는 메타데이터 보존
   ↓
6. Obfuscation normalization (optional) — homoglyph 정규화(canonical 반영), leetspeak/구분자삽입/인코딩된 페이로드 탐지(기본은 플래그만)
   ↓
7. Language / structural metadata extraction — 언어 판별(스크립트 휴리스틱 우선, ja/zh 애매 케이스만 경량 폴백), 구조 힌트
   ↓
Normalized View (NormalizationResult)
```

## 출력: 리치 감사 객체

단순 문자열이 아니라 `NormalizationResult`를 반환한다:

- `normalized_text` — 정규화된 표준 텍스트 (canonical, 보수적으로 변형)
- `normalized_variants` — 매칭 목적의 공격적 정규화 후보 (예: leetspeak/구분자 제거 버전)
- `transformations` — 각 단계에서 적용된 변환 내역 (감사/디버깅용)
- `flags` — 의심스러운 패턴 탐지 결과 (`homoglyph`, `tag_char_smuggling`, `bidi_override`, `encoded_payload`, `leetspeak`, `separator_injection`, `excessive_repetition`, `mixed_script` 등). 판정/스코어링은 하지 않고 신호만 제공.
- `language` — 판별된 언어, 스크립트 비율, 구조적 힌트(HTML/마크다운/URL 포함 여부 등)
- `span_map` — 정규화된 텍스트 위치 ↔ 원본 텍스트 위치 매핑 (원본에서 어디가 왜 바뀌었는지 하이라이트 가능)

자세한 스키마: [`docs/02-architecture.md`](./docs/02-architecture.md)

## 설계 원칙

1. **결정적이고 감사 가능해야 한다** — 같은 입력/설정/규칙 버전이면 항상 같은 출력, 규칙 데이터 버전을 결과에 기록
2. **보수적 기본값** — 정상 텍스트를 오염시키는 것이 우회 패턴을 놓치는 것보다 나쁘다고 간주. 공격적인 규칙(leetspeak 등)은 canonical text를 건드리지 않고 별도 variant로 제공
3. **파이프라인 전 단계 on/off + 커스텀 단계 플러그인 지원**
4. **순수 CPU, 가벼운 의존성** — GPU/무거운 ML 모델 없이 표준 라이브러리 우선, 필요한 곳만 가벼운 서드파티 허용
5. **실시간 단건 처리 지연시간 우선**

## 예시 (API 초안)

```python
import secnorm

result = secnorm.normalize(text)  # 기본 프리셋: security_balanced

result.normalized_text
result.flags
result.language.primary_language
```

세부 API/프리셋: [`docs/10-api-design.md`](./docs/10-api-design.md)

## 문서

| 문서 | 내용 |
|---|---|
| [docs/01-overview.md](./docs/01-overview.md) | 문제 정의, 목표/범위, 설계 원칙 |
| [docs/02-architecture.md](./docs/02-architecture.md) | 데이터 모델, 파이프라인 실행 모델, span mapping, 확장 구조 |
| [docs/03-step1-unicode-normalization.md](./docs/03-step1-unicode-normalization.md) | 1단계: Unicode 정규화 |
| [docs/04-step2-invisible-control-chars.md](./docs/04-step2-invisible-control-chars.md) | 2단계: 비가시/제어 문자 처리 |
| [docs/05-step3-whitespace-normalization.md](./docs/05-step3-whitespace-normalization.md) | 3단계: 공백 정규화 |
| [docs/06-step4-encoding-escaping.md](./docs/06-step4-encoding-escaping.md) | 4단계: 인코딩/이스케이프 정규화 |
| [docs/07-step5-repeated-characters.md](./docs/07-step5-repeated-characters.md) | 5단계: 반복 문자 정규화 |
| [docs/08-step6-obfuscation-normalization.md](./docs/08-step6-obfuscation-normalization.md) | 6단계: 난독화 정규화 (optional) |
| [docs/09-step7-language-structural-metadata.md](./docs/09-step7-language-structural-metadata.md) | 7단계: 언어/구조 메타데이터 추출 |
| [docs/10-api-design.md](./docs/10-api-design.md) | 공개 API, 설정, 프리셋 |
| [docs/11-dependencies.md](./docs/11-dependencies.md) | 의존성 정책과 단계별 선택 라이브러리 |
| [docs/12-testing-strategy.md](./docs/12-testing-strategy.md) | 테스트/평가 전략 |
| [docs/13-roadmap.md](./docs/13-roadmap.md) | 구현 단계(phase)와 v1 범위 |

## 현재 상태

`docs/13-roadmap.md` Phase 0(프로젝트 뼈대) 진행 중. 핵심 데이터 모델, 파이프라인 실행 모델, span mapping은 구현됐고 실제 정규화 단계(1~7단계)는 아직 없음.
