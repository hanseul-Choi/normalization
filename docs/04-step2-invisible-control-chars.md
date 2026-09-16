# 04. 2단계 — Invisible / Control Character Handling

## 목적

눈에 보이지 않는 문자를 이용해 (1) 필터를 우회하거나 (2) 사람 눈에는 안 보이지만 시스템(특히 LLM)에는 읽히는 내용을 숨기는 시도를 정규화/탐지한다. 이 라이브러리의 보안 시나리오에서 가장 중요도가 높은 단계 중 하나.

## 대상 카테고리

Unicode General Category 기준으로 분류하고, 카테고리별로 정책을 다르게 적용한다.

| 카테고리 | 예시 | 기본 정책 |
|---|---|---|
| `Cc` (Control) | `\x00`-`\x1F` (탭/개행 제외), `\x7F` | 제거 + `medium` 플래그 |
| `Cf` (Format) — zero-width | ZWSP `U+200B`, ZWNJ `U+200C`, ZWJ `U+200D`, word joiner `U+2060`, soft hyphen `U+00AD` | 제거 + `medium` 플래그 (단, ZWNJ/ZWJ가 실제 서체 결합에 쓰이는 언어 문맥(아랍어 등)에서는 예외 — v1 지원 언어(ko/en/ja/zh)에는 해당 사례가 없어 기본은 제거) |
| `Cf` — bidi control | LRE/RLE/LRO/RLO/PDF `U+202A`-`U+202E`, LRI/RLI/FSI/PDI `U+2066`-`U+2069` | 제거 + **`high`** 플래그 (`bidi_override`) — 파일명/도메인/텍스트 표시 순서를 조작해 사용자를 속이는 "Trojan Source"류 공격에 사용됨 |
| `Cf` — BOM | `U+FEFF` | 문자열 맨 앞에만 있으면 조용히 제거(인코딩 부산물), 중간에 있으면 제거 + `low` 플래그 |
| **Unicode Tag 문자** | `U+E0000`-`U+E007F` | 제거 + **`high`** 플래그 (`tag_char_smuggling`) — 2024년 이후 알려진 LLM 프롬프트 인젝션 기법("ASCII smuggling"): 화면에는 전혀 안 보이지만 태그 문자로 인코딩된 아스키 텍스트를 프롬프트에 숨겨 전달하는 수법. 이 단계에서 최우선으로 다룬다. |
| **Variation Selector (특히 VS supplement)** | `U+FE00`-`U+FE0F`, `U+E0100`-`U+E01EF` | 이모지 뒤에 정상적으로 붙는 `U+FE0F`(emoji presentation) 등은 허용, 그 외 문맥(일반 문자 뒤에 연속 사용, 특히 VS supplement 블록)은 제거 + `high` 플래그 (`tag_char_smuggling`으로 통합 분류) — 최근 보고된 variation-selector 기반 스테가노그래피 인코딩 대응 |
| `Co` (Private Use Area) | `U+E000`-`U+F8FF` 등 | 기본 유지 (커스텀 이모지/아이콘 폰트 등 정상 사용 사례 존재), `low` 플래그만 |
| `Cn` (미할당 코드포인트) | 현재 Unicode 표준에 없는 코드포인트 | 제거 + `low` 플래그 |
| 기타 비정상 공백류 문자 | Mongolian vowel separator `U+180E`, Hangul filler `U+3164`, `U+FFA0` (한글 반각 필러) | 제거 + `medium` 플래그 (`U+3164`/`U+FFA0`는 한글 자모를 시각적으로 감추는 데 실제로 악용된 사례가 있음) |

## 정책 파라미터

```python
@dataclass
class InvisibleControlStepConfig:
    strip_control: bool = True
    strip_zero_width: bool = True
    strip_bidi_override: bool = True       # 끄는 것을 권장하지 않음
    strip_tag_chars: bool = True           # 끄는 것을 권장하지 않음
    strip_variation_selectors: Literal["suspicious_only", "all", "none"] = "suspicious_only"
    strip_unassigned: bool = True
    private_use_policy: Literal["keep", "flag", "strip"] = "flag"
    preserve_whitelist: set[str] = field(default_factory=lambda: {"\t", "\n"})
```

`preserve_whitelist`는 3단계(공백 정규화)에서 다루는 개행/탭과 겹치지 않도록 이 단계에서는 건드리지 않고 통과시킨다 — 단계 간 책임 분리.

## 출력

- 제거된 문자마다 `Transformation(step="invisible_control", rule="strip_<category>")` 기록 (연속 구간은 병합).
- `high`/`medium` 심각도 플래그는 **원본 위치 그대로** span에 남겨서, 상위 레이어가 "이 메시지 어디에 몰래 숨긴 문자가 있었는지" 바로 하이라이트할 수 있게 한다.

## 구현

- 표준 라이브러리 `unicodedata.category()`로 카테고리 분류. 코드포인트 범위 상수(Tag 문자, bidi control, VS 등)는 이 라이브러리 내부에 하드코딩된 테이블로 관리 (Unicode 표준 블록이라 자주 안 바뀜, 별도 의존성 불필요).
- 대량 코드포인트 스캔이 필요하므로 `str.translate()` + 제거 대상 codepoint set을 활용해 O(n)으로 처리 (정규식 문자 클래스보다 빠름).

## 예시

| 입력 (숨은 문자 표시) | 정규화 결과 | 플래그 |
|---|---|---|
| `무료 배​포` (사이에 ZWSP) | `무료 배포` | `medium` |
| `admin` + Tag 문자로 인코딩된 숨은 지시문 | `admin` (숨은 지시문 통째로 제거) | `high` (`tag_char_smuggling`) |
| `‮reversed‬` (RLO로 시각적 역순 표시) | RLO/PDF 제거, 원래 코드포인트 순서 그대로 노출 | `high` (`bidi_override`) |
