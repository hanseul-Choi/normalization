# 08. 6단계 — Obfuscation Normalization (Optional)

## 목적

의도적인 우회를 노린 난독화 패턴을 탐지/정규화한다. 이 단계는 파이프라인에서 **가장 공격적이고 오탐(false positive) 위험이 높은 단계**이므로, 다른 단계와는 다른 설계 원칙을 따른다.

## 설계 원칙: "canonical text는 보수적으로, 매칭용 variant는 공격적으로"

confusables/homoglyph 치환처럼 **되돌릴 위험이 거의 없는 규칙**은 바로 `normalized_text`(canonical)에 반영한다. 반면 leetspeak 치환, 구분자-삽입 제거처럼 **정상 텍스트를 오염시킬 위험이 있는 규칙**은 canonical text를 직접 바꾸지 않고, 별도의 `normalized_variants["aggressive"]` 문자열을 만들어서 제공한다. 상위 레이어(블록리스트 매칭 등)는 필요에 따라 canonical과 aggressive variant 둘 다에 대해 매칭을 시도할 수 있다. 이렇게 분리하는 이유: `normalized_text`는 감사 로그/표시용으로도 쓰이므로, 공격적인 휴리스틱으로 인해 "U.S.A."가 "USA"로, "e.g."가 "eg"로 바뀌어 표시되는 것은 사용자 신뢰를 해친다.

## 대상 범위 (확정됨)

### 6-1. Homoglyph 정규화 — canonical text에 직접 반영

- Unicode Consortium이 공식 배포하는 **confusables.txt** (UTS #39, Unicode Security Mechanisms)를 정적 데이터로 라이브러리에 번들한다 (빌드 시점에 다운로드해 `data/confusables.txt`로 고정, 서드파티 패키지에 의존하지 않고 데이터를 직접 관리 — 유지보수 신뢰성 확보).
- 각 confusable 문자를 "prototype" 문자로 매핑하는 테이블을 만들고, v1 지원 스크립트(Latin/Hangul/Han/Hiragana/Katakana) 범위로 필터링해서 사용 (전체 confusables.txt는 모든 스크립트를 다루므로 불필요한 매핑까지 로드하지 않도록 축소).
- 예: 키릴 `а` (U+0430) → 라틴 `a`, 그리스 `ο` (U+03BF) → 라틴 `o`.
- 치환이 일어나면 `Transformation(step="obfuscation", rule="homoglyph_normalize")` + **항상** `SuspicionFlag(category="homoglyph", severity="high")` 생성 — 정상적인 텍스트에 다른 스크립트의 룩얼라이크 문자가 섞여 있는 경우는 거의 없으므로 확신도가 높음.
- 단일 스크립트로 일관된 텍스트(예: 순수 키릴 문장)는 대상에서 제외 — "섞여있을 때"만 의심스러움 (판별은 7단계의 `script_ratios`를 먼저 계산해서 이 단계에 전달하는 방식으로 구현 — 파이프라인 순서상 7단계가 뒤에 있으므로, 이 단계 내부에서 경량 스크립트 비율을 자체 계산하거나, 파이프라인을 2-pass로 구성 — `아키텍처 문서 02`의 `PipelineContext.language` 필드를 미리 채우는 "prepass" 방식 채택).

### 6-2. 글자 사이 구분자 삽입 — aggressive variant에만 반영

- `f.r.e.e`, `f r e e`, `f-r-e-e`, `f_r_e_e` 처럼 단일 문자(또는 단일 자모/음절)마다 구분자가 규칙적으로 삽입된 패턴을 탐지.
- 휴리스틱: 길이 4 이상의 "단일문자+구분자" 반복 시퀀스를 정규식으로 탐지 (`(\w[\s._\-]){4,}\w`). 오탐이 큰 규칙(`U.S.A.`, `e.g.`, `1.2.3` 버전 문자열 등)이므로:
  - 기본은 **탐지만 하고 플래그만 생성** (`SuspicionFlag(category="separator_injection", severity="low")`), canonical text는 건드리지 않음.
  - 구분자 제거 결과를 `normalized_variants["aggressive"]`에 넣어서, 상위 레이어가 "구분자를 제거했을 때 블록리스트 단어와 일치하는가"를 판단하는 데 쓸 수 있게 한다.
  - 옵션 `require_dictionary_match=True`(기본 off): 구분자를 제거한 결과가 사전/블록리스트에 있는 알려진 토큰과 일치할 때만 canonical text에도 반영하는 상위 통합 모드 지원 (사전은 이 라이브러리가 내장하지 않고, 외부에서 `dictionary: set[str]`로 주입받는 형태 — 라이브러리 자체는 금칙어 사전을 갖지 않는다).

### 6-3. Leetspeak / 시각적 치환 — aggressive variant에만 반영

- 숫자/기호 → 문자 치환 매핑 테이블 내장: `0→o, 1→i/l, 3→e, 4→a, 5→s, 7→t, @→a, $→s, €→e` 등 (다대일 매핑은 가장 흔한 케이스 우선, ambiguous한 경우 여러 후보 생성 가능하도록 설계는 하되 v1은 최빈 치환 1개만 적용).
- 오탐 위험이 매우 크므로(`l33t`가 아니라 실제 숫자/코드/전화번호/제품명이 포함된 정상 텍스트가 흔함) **항상 aggressive variant 전용**. canonical text에는 절대 반영하지 않는다.
- 치환이 3개 이상 문자에 걸쳐 발생하면 `SuspicionFlag(category="leetspeak", severity="low")` 생성 (단발성 치환은 플래그도 생성하지 않음 — "4"라는 단일 문자 하나로는 신호가 너무 약함).

### 6-4. 인코딩된 페이로드 탐지 (확정됨: 탐지만, decode는 기본 off)

- Base64/hex/quoted-printable로 보이는 하위 문자열을 정규식 휴리스틱(문자셋, 길이, 패딩 패턴)으로 탐지.
- 기본 동작: **탐지 후 플래그만 생성** (`SuspicionFlag(category="encoded_payload", severity="medium")`). 디코딩은 하지 않음 — 이유: (1) 디코딩 결과가 텍스트가 아닐 수 있음(바이너리), (2) 재귀적으로 파이프라인에 태우면 비용/증폭 공격(zip bomb류) 위험.
- 옵션 `decode_and_recurse=True`(기본 off, 명시적 opt-in): 디코딩 성공 + 결과가 유효 UTF-8 텍스트인 경우에 한해 파이프라인을 재귀 실행. **반드시 다음 안전장치와 함께 사용**:
  - `max_recursion_depth` (기본 1)
  - `max_decoded_size` (원본 대비 배율 제한, 예: 10배)
  - 재귀 결과에서 발견된 플래그는 `metadata={"source": "decoded_payload", "depth": n}`로 원본과 구분해서 기록.

## 프리셋별 기본 on/off

- `security_strict`: 6단계 전체 on, `decode_and_recurse` on, `require_dictionary_match` off (가장 많이 탐지, 가장 많은 플래그)
- `security_balanced` (기본): homoglyph만 canonical 반영 on, 나머지는 탐지(플래그)만, `decode_and_recurse` off
- `nlp_preprocessing` / `minimal`: 6단계 전체 off

## 정책 파라미터

```python
@dataclass
class ObfuscationStepConfig:
    enabled: bool = True
    homoglyph_normalize: bool = True
    separator_injection_detect: bool = True
    separator_injection_collapse_in_canonical: bool = False
    leetspeak_detect: bool = True
    encoded_payload_detect: bool = True
    decode_and_recurse: bool = False
    max_recursion_depth: int = 1
    max_decoded_size_ratio: float = 10.0
    dictionary: frozenset[str] | None = None   # 외부 주입, 라이브러리는 내용을 갖지 않음
```

## 구현 / 의존성

- confusables 데이터: Unicode.org 공식 `confusables.txt`를 번들 (라이선스: Unicode License, 재배포 허용). 로더는 자체 구현 (파싱 로직이 단순해 서드파티 불필요).
- 정규식: `regex` 모듈 (유니코드 스크립트 속성 `\p{Script=Latin}` 등 필요).
- base64/hex 탐지: 표준 `re` + `base64` 모듈로 충분.

## 예시

| 입력 | canonical `normalized_text` | `normalized_variants["aggressive"]` | 플래그 |
|---|---|---|---|
| `аdmin` (첫 글자 키릴 а) | `admin` | (동일) | `homoglyph` (high) |
| `f r e e   m o n e y` | `f r e e   m o n e y` (그대로) | `free money` | `separator_injection` (low) |
| `h3ll0 w0rld` | `h3ll0 w0rld` (그대로) | `hello world` | `leetspeak` (low) |
| `설치는 aGVsbG8gd29ybGQ= 여기서` | 그대로 (decode_and_recurse=False 기준) | — | `encoded_payload` (medium) |
