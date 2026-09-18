# 02. 아키텍처

## 핵심 데이터 모델

모두 `dataclasses` 기반 (의존성 최소화 원칙, `11-dependencies.md` 참고). `slots=True`로 메모리/속도 최적화.

```python
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["low", "medium", "high"]

@dataclass(slots=True, frozen=True)
class Span:
    start: int
    end: int

@dataclass(slots=True, frozen=True)
class Transformation:
    step: str                # 예: "unicode_normalization"
    rule: str                # 예: "NFKC", "strip_zero_width_space"
    original: str
    replacement: str
    span_before: Span        # 이 단계 입력 기준 좌표
    span_after: Span         # 이 단계 출력 기준 좌표
    metadata: dict = field(default_factory=dict)

@dataclass(slots=True, frozen=True)
class SuspicionFlag:
    category: str            # "homoglyph" | "zero_width_injection" | "bidi_override"
                              # | "tag_char_smuggling" | "encoded_payload"
                              # | "leetspeak" | "separator_injection"
                              # | "excessive_repetition" | "mixed_script"
    severity: Severity
    step: str
    span: Span                # 원본(raw_text) 좌표
    detail: str
    metadata: dict = field(default_factory=dict)

@dataclass(slots=True, frozen=True)
class LanguageMetadata:
    primary_language: str | None       # "ko" | "en" | "ja" | "zh" | None
    language_confidence: float
    script_ratios: dict[str, float]    # {"Hangul": 0.8, "Latin": 0.2, ...}
    is_mixed_script: bool
    structural: "StructuralHints"

@dataclass(slots=True, frozen=True)
class StructuralHints:
    has_html: bool
    has_markdown: bool
    has_url: bool
    has_email: bool
    has_code_block: bool
    sentence_count: int
    word_count: int
    direction: Literal["ltr", "rtl", "mixed"]

@dataclass(slots=True, frozen=True)
class NormalizationResult:
    raw_text: str
    normalized_text: str
    normalized_variants: dict[str, str]   # 예: {"aggressive": "..."} (08 참고)
    transformations: list[Transformation]
    flags: list[SuspicionFlag]
    language: LanguageMetadata
    span_map: "SpanMap"
    config_name: str
    pipeline_version: str
    rule_data_version: dict[str, str]     # 예: {"confusables": "16.0.0"}
```

`Transformation`과 `SuspicionFlag`를 분리한 이유: 모든 변환이 의심스러운 건 아니고(예: 단순 공백 trim), 모든 의심 신호가 텍스트 변환을 동반하는 것도 아니다(예: mixed-script 탐지는 플래그만 남기고 텍스트는 안 바꿀 수 있음).

## 파이프라인 실행 모델

각 단계(step)는 순수 함수에 가까운 형태로 구현한다.

```python
class PipelineStep(Protocol):
    name: str

    def apply(self, ctx: "PipelineContext") -> "StepOutput":
        ...

@dataclass
class PipelineContext:
    raw_text: str              # 원본, 절대 변경 안 됨
    text: str                  # 현재까지 정규화된 텍스트 (단계 진행하며 갱신)
    config: "NormalizationConfig"
    span_map: "SpanMap"        # 누적 매핑, 단계마다 갱신
    language: LanguageMetadata | None = None   # 7단계 이후 채워짐, 이후 단계에서 참조 가능

@dataclass
class StepOutput:
    text: str
    transformations: list[Transformation]
    flags: list[SuspicionFlag]
    edits: list["Edit"]        # span_map 갱신용 (아래 참고)
```

`NormalizationPipeline`은 `PipelineStep` 목록을 순서대로 실행하며 `PipelineContext`를 갱신한다.

```python
class NormalizationPipeline:
    def __init__(self, steps: list[PipelineStep], config: NormalizationConfig): ...

    def run(self, text: str) -> NormalizationResult: ...
    # 결정성 및 멱등성 보장: 보안 지향 프리셋(security_strict, security_balanced, llm_input_sanitize)은
    # stabilize_output=True 설정을 통해 출력 텍스트가 더 이상 변하지 않을 때까지(fixpoint)
    # 최대 N회(기본 3회) 파이프라인을 재실행하여 디코딩 후 새로 노출된 위험 요소까지 완전히 제거하고
    # 모든 플래그/변환을 원본 raw_text 좌표계로 합성(compose)한다.

    # 확장성 (확정됨: 단계별 on/off + 커스텀 단계 플러그인)
    def enable(self, step_name: str) -> None: ...
    def disable(self, step_name: str) -> None: ...
    def insert_step(self, step: PipelineStep, *, after: str | None = None,
                     before: str | None = None) -> None: ...
    def replace_step(self, step_name: str, step: PipelineStep) -> None: ...

    @classmethod
    def from_preset(cls, name: str) -> "NormalizationPipeline": ...
```

기본 7단계는 각각 `name`이 고정되어 있다: `unicode`, `invisible_control`, `whitespace`, `encoding_escaping`, `repeated_char`, `obfuscation`(기본 off 여부는 프리셋에 따름), `language_structural`. `insert_step`/`replace_step`으로 이 이름들을 기준점으로 삼아 커스텀 단계를 앞뒤에 끼워 넣는다.

## Span Mapping (원본 ↔ 정규화 위치 매핑)

보안 감사 시나리오에서는 "정규화된 텍스트의 어느 부분이, 원본의 어느 부분에서, 왜 바뀌었는지"를 역추적할 수 있어야 한다. 각 단계는 텍스트를 바꿀 때마다 그 단계의 입력/출력 좌표계 기준 "edit list"를 함께 반환한다.

```python
@dataclass(slots=True, frozen=True)
class Edit:
    src_span: Span   # 이 단계 입력 텍스트 기준
    dst_span: Span   # 이 단계 출력 텍스트 기준
```

`SpanMap`은 여러 단계에 걸친 edit list를 순차 합성(compose)해서, 최종적으로 "normalized_text 좌표 → raw_text 좌표"를 얻을 수 있게 한다. 합성 알고리즘은 표준적인 텍스트 정렬(alignment) 기법을 사용한다: 변경되지 않은 구간은 항등 매핑으로 유지하고, 변경된 구간은 해당 edit의 `src_span`으로 뭉뚱그려 매핑한다(문자 단위 정밀 diff는 하지 않음 — 단계 내부에서 이미 최소 단위 edit을 생성하므로 충분히 정밀함).

```python
class SpanMap:
    def to_raw(self, normalized_span: Span) -> Span: ...
    def to_normalized(self, raw_span: Span) -> Span | None: ...
    def compose(self, edits: list[Edit]) -> "SpanMap": ...
```

이 매핑이 있으면, 예를 들어 6단계에서 homoglyph 치환이 일어난 지점을 원본 텍스트 하이라이트로 그대로 보여줄 수 있다.

## 설정 (`NormalizationConfig`)

단계별 파라미터를 담는 최상위 설정 객체. 프리셋 + 부분 오버라이드 방식을 지원한다.

```python
@dataclass
class NormalizationConfig:
    enabled_steps: set[str]
    unicode: UnicodeStepConfig
    invisible_control: InvisibleControlStepConfig
    whitespace: WhitespaceStepConfig
    encoding_escaping: EncodingEscapingStepConfig
    repeated_char: RepeatedCharStepConfig
    obfuscation: ObfuscationStepConfig
    language_structural: LanguageStructuralStepConfig
```

각 `*StepConfig`는 해당 단계 문서(`03`~`09`)에서 정의한다. JSON/TOML로 직렬화 가능해야 하며 (`json`/`tomllib` 표준 라이브러리 사용), 이를 통해 설정을 코드 밖에서 관리할 수 있다.

## 오류 처리 원칙

- 각 단계는 **입력에 대해 total function**이어야 한다 — 즉, 어떤 malformed/이상한 유니코드 입력이 와도 예외를 던지지 말고 처리하거나 그대로 통과시켜야 한다 (예외를 던지는 것은 보안 파이프라인에서 그 자체로 우회/DoS 벡터가 된다).
- 잠재적으로 비용이 큰 연산(정규식 백트래킹, 재귀적 디코딩 등)에는 반드시 길이 제한과 재귀 깊이 제한을 둔다 (ReDoS/증폭 공격 방지, `08-step6-obfuscation-normalization.md`의 인코딩된 페이로드 탐지 참고).
- 단계 실행 중 개별 규칙이 실패해도 파이프라인 전체가 죽지 않도록 단계 내부에서 규칙 단위로 격리한다.

## 버전/재현성

`NormalizationResult.pipeline_version`과 `rule_data_version`(예: confusables 데이터 버전)을 항상 기록한다. 규칙 데이터가 갱신되면 과거에 생성된 감사 로그와 현재 결과를 구분할 수 있어야 하기 때문이다 — 보안 감사 로그는 "그 당시 어떤 규칙으로 판단했는지"가 중요하다.
