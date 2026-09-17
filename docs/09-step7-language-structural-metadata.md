# 09. 7단계 — Language / Structural Metadata Extraction

## 목적

정규화된 텍스트로부터 언어/스크립트/구조에 대한 메타데이터를 뽑아낸다. 이 단계는 텍스트 자체를 변형하지 않고(원칙적으로 `Transformation`을 생성하지 않음) `LanguageMetadata`를 채운다. 단, 6단계 homoglyph 판별이 스크립트 비율 정보를 필요로 하므로, **스크립트 비율 계산만 경량 prepass로 6단계 이전에 먼저 수행**하고 (`02-architecture.md`의 `PipelineContext.language` prepass 참고), 언어 판별/구조 추출 같은 나머지는 정식 7단계 자리에서 수행한다.

## 7-1. 스크립트 비율 계산 (경량, 의존성 없음)

- 각 문자의 Unicode Script 속성(Hangul / Latin / Han / Hiragana / Katakana / Common / 기타)을 세어 비율(`script_ratios: dict[str, float]`)을 계산.
- 구현: `unicodedata`에는 Script 속성이 없으므로, 코드포인트 범위 테이블을 자체 구축 (Hangul: `U+AC00`-`U+D7A3` + 자모 블록, Han: CJK Unified Ideographs 관련 블록들, Hiragana/Katakana: 각 블록, Latin: 기본 라틴 + Latin-1 Supplement + Extended). 4개 언어 한정이므로 전체 Unicode Script 데이터베이스를 갖다 쓸 필요 없이 필요한 블록만 하드코딩 — 빠르고 의존성 없음.
- `is_mixed_script`: 상위 2개 스크립트의 비율이 모두 15% 이상이면 True (단, `Common`/`Inherited`처럼 숫자/구두점 등 스크립트 중립 문자는 분모/분자에서 제외하고 계산).

## 7-2. 언어 판별 (v1: ko/en/ja/zh 한정, 하이브리드 전략)

**1차: 스크립트 기반 규칙 (의존성 없음, 대부분의 케이스를 커버)**

| 조건 | 판정 |
|---|---|
| Hangul 비율이 우세 | `ko` |
| Hiragana 또는 Katakana가 조금이라도 유의미하게 존재 | `ja` (가나가 있으면 한자가 섞여 있어도 일본어로 확신 가능 — 중국어는 가나를 쓰지 않음) |
| Han(한자)만 있고 가나/한글 없음 | 애매한 케이스 → CJK 고유 마커 1차 판정 후 2차 langdetect 폴백 (`ja` vs `zh`) |
| Cyrillic이 우세 | `ru` |
| Greek이 우세 | `el` |
| Arabic이 우세 | `ar` (RTL 텍스트) |
| Hebrew가 우세 | `he` (RTL 텍스트) |
| Latin이 우세 | `en`, `es`, `fr`, `de` (유럽어 특수 마커/다이어크리틱 1차 판정 후 2차 langdetect 폴백, 기본: `en`) |

**2차: 애매한 케이스 및 다국어 세부 판별 (ja vs zh, 유럽 라틴어군 등)**

- 이 경우만 가벼운 통계 기반 언어감지 라이브러리로 폴백 (`langdetect` 등, `11-dependencies.md` 참고). 순수 한자 또는 라틴 다국어 문자열에서 고유 마커로 확정할 수 없는 케이스에만 선별 적용해 평균 지연시간에 미치는 영향을 최소화.
- 폴백 판정도 실패하면 (텍스트가 너무 짧음 등) `primary_language=None`, `language_confidence=0.0`.

이렇게 하이브리드로 설계하는 이유: "CPU 기반, 가벼운 의존성" 원칙에 따라 무거운 언어감지를 기본 경로에서 제거하고 진짜 애매한 극히 일부 케이스에만 쓴다.

## 7-3. 구조적 힌트 추출

| 필드 | 탐지 방법 |
|---|---|
| `has_html` | `<[a-zA-Z][^>]*>` 류 태그 패턴 매치 (4단계에서 이미 entity는 디코딩됐으므로 남은 태그만 보면 됨) |
| `has_markdown` | `**bold**`, `# heading`, `` `code` ``, `[link](url)` 등 흔한 마크다운 문법 패턴 매치 |
| `has_url` | 정규식 기반 URL 패턴 (스킴 있는/없는 도메인 형태 모두 포함) |
| `has_email` | 표준 이메일 정규식 |
| `has_code_block` | 트리플 백틱 또는 4-space 들여쓰기 연속 블록 |
| `sentence_count` | 언어별 문장 종결 부호 기반 단순 분할 (`.!?`, 한중일은 `。！？`) — 무거운 tokenizer 불필요 |
| `word_count` | 라틴/한글은 공백 기준, 한자/가나는 문자 수 근사(형태소 분석기 없이 문자 단위 근사치로 충분 — 정밀 분절은 이 라이브러리 범위 밖) |
| `direction` | 판별된 스크립트 기준 (Arabic, Hebrew 등 RTL 스크립트 우세 시 `"rtl"`, 그 외 `"ltr"`) |

## 출력 예시

```python
LanguageMetadata(
    primary_language="ko",
    language_confidence=0.92,
    script_ratios={"Hangul": 0.85, "Latin": 0.10, "Common": 0.05},
    is_mixed_script=False,
    structural=StructuralHints(
        has_html=False, has_markdown=False, has_url=True, has_email=False,
        has_code_block=False, sentence_count=2, word_count=14, direction="ltr",
    ),
)
```

## 정책 파라미터

```python
@dataclass
class LanguageStructuralStepConfig:
    enabled: bool = True
    mixed_script_threshold: float = 0.15
    fallback_detector: Literal["langdetect", "none"] = "langdetect"
    min_text_length_for_detection: int = 2
```

## 구현 / 의존성

- 스크립트 비율/구조 힌트: 표준 라이브러리(`re`)만으로 구현.
- 2차 폴백 언어감지: `langdetect` (순수 Python, CPU, 가벼움) — `11-dependencies.md`에서 대안(`lingua-language-detector` 등)과 비교.
