# 06. 4단계 — Encoding / Escaping Normalization

## 목적

텍스트 안에 인코딩되어 들어있는 내용(HTML entity, URL percent-encoding, Unicode escape 시퀀스)을 실제 문자로 복원하고, 인코딩이 깨져서(mojibake) 잘못 디코딩된 텍스트를 복구한다. **여기서 다루는 건 "표준 인코딩 스킴을 정확히 따르는" 디코딩이고, base64/hex처럼 페이로드를 통째로 숨기는 용도의 인코딩 탐지는 6단계(난독화 정규화)의 책임이다** — 이 단계와 6단계의 경계를 명확히 구분한다.

## 하위 기능

### 4-1. HTML Entity 디코딩

- `&amp;`, `&lt;`, `&#39;`, `&#x27;` 등을 실제 문자로 변환.
- 표준 라이브러리 `html.unescape()` 사용.
- 디코딩 후 결과에 다시 `<`, `>` 등 HTML 특수문자가 생기면 → 이 자체는 정상(사용자가 HTML entity로 인코딩된 코드 스니펫을 붙여넣었을 수 있음), 플래그는 만들지 않음. 단 7단계 구조 메타데이터의 `has_html` 판단에는 반영.

### 4-2. URL Percent-encoding 디코딩

- `%20`, `%3C` 등을 디코딩. 단, **텍스트 전체가 URL이 아닌 경우** 무분별하게 디코딩하면 정상 텍스트를 훼손할 위험이 있음 (예: `100%20`처럼 우연히 percent-encoding처럼 보이는 문자열). 따라서 아래 휴리스틱을 적용:
  - URL로 보이는 구간(스킴 prefix `http(s)://` 또는 도메인 패턴 매치)만 대상으로 `urllib.parse.unquote()` 적용.
  - URL이 아닌 일반 텍스트 구간에서 `%XX` 패턴이 검출되면 `SuspicionFlag(category="encoded_payload", severity="low")`만 남기고 디코딩은 하지 않음 (오탐 방지, 명시적 opt-in으로만 디코딩하도록 설정 제공).
  - `decode_url_encoding="always"`(예: `security_strict`): 텍스트 전체의 모든 percent-encoding을 무조건 디코딩하고, 검출된 `%XX` 시퀀스마다 `SuspicionFlag(category="encoded_payload", severity="medium", detail="percent_encoding_decoded_always_mode")` 플래그를 생성한다.

### 4-3. Unicode Escape 시퀀스 디코딩

- `\uXXXX`, `\UXXXXXXXX`, `\xXX`, `\N{...}` 형태의 **리터럴 이스케이프 문자열**(실제 유니코드 문자가 아니라 백슬래시+문자로 된 텍스트)을 실제 문자로 디코딩.
- 이건 꽤 강한 신호다: 정상적인 사용자 텍스트에 `http` 같은 패턴이 등장하는 경우는 드물고, 대부분 필터 우회 목적. 따라서 디코딩과 동시에 **항상 플래그 생성**: `SuspicionFlag(category="encoded_payload", severity="medium", detail="unicode_escape_sequence")`.
- 코드 스니펫 공유 등 정상 사용 사례(예: 개발자 커뮤니티)를 고려해 `unicode_escape_policy`로 "decode_and_flag"(기본) / "flag_only"(디코딩 안 하고 원문 유지) / "ignore" 선택 가능.

### 4-4. Mojibake 복구 (선택)

- 잘못된 인코딩 왕복(예: UTF-8 바이트를 Latin-1/CP1252로 잘못 해석 후 재인코딩)으로 깨진 텍스트(`ë`, `â€™` 같은 패턴)를 원래 문자로 복구.
- 이 기능은 **정확도가 100%가 아니고 휴리스틱**이므로 기본은 off. 켜면 `Transformation(step="encoding_escaping", rule="mojibake_repair")`와 함께 `metadata`에 신뢰도 점수 기록.
- 원시 바이트(`bytes`) 입력이 주어지는 경우(문자열이 아니라)에는 이 단계 이전에 인코딩 자체를 감지해서 올바르게 디코딩하는 것이 우선 (파이프라인은 `str` 입력을 기본 전제로 하고, `bytes` 입력을 받는 진입점에서 인코딩 감지 라이브러리로 1차 디코딩 후 파이프라인에 태움 — `11-dependencies.md` 참고).

## 정책 파라미터

```python
@dataclass
class EncodingEscapingStepConfig:
    decode_html_entities: bool = True
    decode_url_encoding: Literal["url_context_only", "always", "off"] = "url_context_only"
    unicode_escape_policy: Literal["decode_and_flag", "flag_only", "ignore"] = "decode_and_flag"
    mojibake_repair: bool = False
```

## 구현

- HTML entity: `html.unescape` (표준 라이브러리)
- URL: `urllib.parse.unquote` (표준 라이브러리) + 정규식으로 URL 구간 탐지
- Unicode escape: 표준 라이브러리 `codecs.decode(text, "unicode_escape")`는 바이트 왕복 이슈가 있어 한글 등 비ASCII 원문을 깨뜨릴 수 있음 → 직접 정규식으로 `\uXXXX`/`\xXX` 패턴만 안전하게 치환하는 자체 구현 사용 (원문에 이미 있는 비ASCII 문자는 손대지 않음).
- Mojibake 복구: `ftfy` 라이브러리 사용 권장 (순수 CPU, 이 문제를 위해 만들어진 성숙한 라이브러리). `11-dependencies.md` 참고.

### 구현 노트

- 이 단계는 내부적으로 여러 하위 변환(HTML entity → URL → Unicode escape → mojibake)을 순차 적용한다. 각 하위 변환은 자신의 입력/출력을 diff해서 얻은 edit을 스크래치 `SpanMap`에 누적 합성(compose)하는 방식으로, 최종적으로 이 *단계 전체*의 입력(`ctx.text`)/출력 기준 좌표로 표현된 `Transformation`/`Edit`를 만든다 (`docs/02-architecture.md`의 "이 단계 입력/출력 기준 좌표" 규칙을 단일 단계 내부의 다단계 처리에도 지키기 위함). 두 하위 변환이 정확히 같은 원본 구간을 연달아 바꾸는 극단적인 경우(예: HTML entity로 디코딩된 결과가 우연히 URL percent-encoding처럼 보이는 경우)는 `Transformation`은 각각 남기되 `Edit`는 최종 매핑 하나로 합쳐 반환한다 — 부분적으로 겹치지만 동일하지는 않은 구간까지 정교하게 병합하지는 않는다 (Phase 1 범위 밖으로 유보).
- `ftfy`는 문서가 언급한 "신뢰도 점수" 같은 단일 지표를 제공하지 않는다. 대신 `ftfy.fix_and_explain()`이 반환하는 적용된 복구 연산 목록을 `Transformation.metadata["ftfy_operations"]`에 그대로 기록한다.
- `mojibake_repair=True`인데 `ftfy`가 설치돼 있지 않으면(옵션 의존성, `docs/11-dependencies.md`) 예외를 던지지 않고 그 하위 기능만 조용히 건너뛴다 (`docs/02-architecture.md`의 "각 단계는 total function이어야 한다" 원칙).

## 예시

| 입력 | 출력 | 플래그 |
|---|---|---|
| `AT&amp;T` | `AT&T` | 없음 |
| `https://example.com/%ED%95%9C%EA%B8%80` | `https://example.com/한글` | 없음 (URL 컨텍스트) |
| `100%20 할인` (URL 문맥 아님) | `100%20 할인` (디코딩 안 함) | `low` (`encoded_payload`) |
| `..%2f..%2fetc%2fpasswd` (`always` 모드) | `../../etc/passwd` | `medium` (`encoded_payload`) |
| `café` 원문에 섞인 정상 한글 `안\uub155` | 정책에 따라 디코딩 (`\uub155`→`녕`) + 플래그 | `medium` |
