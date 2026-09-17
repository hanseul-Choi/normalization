# secnorm

의도적으로 난독화되거나 변형된 텍스트를 **표준화된 정규화 뷰(Normalized View)** 로 수렴시키는 CPU 기반 Python 라이브러리.

---

## 주요 기능

1. **결정적이고 감사 가능한 정규화**:
   - 동일 입력/설정에 대해 항상 100% 동일한 결과 보장.
   - 원본 위치 ↔ 정규화 위치를 완벽히 역추적하는 `SpanMap` 제공.
2. **7단계 보안 지향 파이프라인**:
   - **Step 1: Unicode Normalization** (NFKC/NFC, 전각/호환 문자 표준화)
   - **Step 2: Invisible/Control Characters** (Zero-width, Bidi override, Unicode Tag/스머글링, VS, 미할당/PUA 처리)
   - **Step 3: Whitespace Normalization** (각종 공백 통일, strict/structural 단락 보존 모드)
   - **Step 4: Encoding/Escaping** (HTML entity, URL percent-encoding, unicode escape, ftfy mojibake 복구)
   - **Step 5: Repeated Characters** (카테고리별 반복 상한, 한글 자모/구두점/이모지 처리, excessive_repetition 플래그)
   - **Step 6: Obfuscation Normalization** (UTS #39 Confusables 기반 Homoglyph, 구분자 삽입, Leetspeak, Base64/Hex 페이로드 탐지 및 재귀 정규화)
   - **Step 7: Language & Structural Metadata** (ko/en/ja/zh 하이브리드 언어 판별, 스크립트 비율, 구조적 힌트)
3. **5종 표준 프리셋 제공**:
   - `security_balanced` (기본값): 실서비스 표준. Homoglyph만 canonical 반영, 구분자/Leetspeak은 플래그 및 aggressive variant 제공.
   - `security_strict`: 스팸/우회 탐지 최우선. 구분자 제거 canonical 반영 및 Base64 페이로드 재귀 정규화 활성화.
   - `llm_input_sanitize`: LLM 프롬프트 인젝션 방어. Variation Selector 및 Bidi/Tag 스머글링 집중 정제.
   - `nlp_preprocessing`: 검색/분류 등 일반 NLP용. 1~5단계 on, 6단계 off, structural 공백 모드.
   - `minimal`: Unicode NFC + 공백 trim 최소 정규화.
4. **플러그인 아키텍처**:
   - `pipeline.insert_step(..., after=...)`, `pipeline.replace_step(...)` 등을 통해 자유롭게 커스텀 단계 추가.
5. **순수 CPU & 경량 의존성**:
   - GPU/무거운 ML 모델 없음. 표준 라이브러리 우선 및 빠른 실행 속도.

---

## 빠른 시작 (Quick Start)

### 기본 사용법

```python
import secnorm

# 기본 프리셋: security_balanced
result = secnorm.normalize("  héllo   wörld!  ")
print(result.normalized_text)  # "hello world!"
print(result.language.primary_language)  # "en"
```

### 보안 감사 및 우회 탐지

```python
import secnorm

# 키릴 문자 'а'가 포함된 피싱 도메인
result = secnorm.normalize("аpple.com", preset="security_balanced")

print(result.normalized_text)  # "apple.com" (라틴 문자로 정규화)
for flag in result.flags:
    print(f"[{flag.severity.upper()}] {flag.category}: {flag.detail} (span: {flag.span})")
# [HIGH] homoglyph: homoglyph_а_to_a (span: Span(start=0, end=1))
```

### Aggressive Variant 활용

```python
import secnorm

# 구분자 삽입 및 Leetspeak 스팸
result = secnorm.normalize("f.r.e.e  m.0.n.e.y", preset="security_balanced")

# Canonical 텍스트는 보수적으로 원형 유지
print(result.normalized_text)  # "f.r.e.e m.0.n.e.y"

# 필터링/블랙리스트 매칭용 aggressive variant
print(result.normalized_variants["aggressive"])  # "free money"
```

### 배치 처리

```python
results = secnorm.normalize_batch(
    ["Hello   world", "аpple.com", "coooool!"],
    preset="security_balanced",
    n_jobs=2,
)
```

---

## 커스텀 단계 플러그인 (Custom Steps)

`PipelineStep` 프로토콜을 구현하여 파이프라인 전/후에 커스텀 단계를 삽입할 수 있습니다:

```python
from secnorm import PipelineContext, StepOutput, Pipeline
from secnorm.models import Span, SuspicionFlag
from secnorm.spanmap import Edit

class ProfanityMaskStep:
    name = "profanity_mask"

    def apply(self, ctx: PipelineContext) -> StepOutput:
        text = ctx.text
        if "badword" not in text:
            return StepOutput(text=text)
        
        start = text.index("badword")
        new_text = text.replace("badword", "***")
        return StepOutput(
            text=new_text,
            edits=[Edit(src_span=Span(start, start + 7), dst_span=Span(start, start + 3))],
            flags=[SuspicionFlag(
                category="profanity",
                severity="medium",
                step=self.name,
                span=ctx.span_map.to_raw(Span(start, start + 7)),
                detail="badword detected",
            )]
        )

pipeline = Pipeline.from_preset("security_balanced")
pipeline.insert_step(ProfanityMaskStep(), after="obfuscation")

result = pipeline.run("This contains badword!")
print(result.normalized_text)  # "This contains ***!"
```

---

## CLI 사용법

```bash
# 기본 텍스트 정규화
secnorm "Hello    world!"

# 프리셋 지정
secnorm "аpple.com" --preset security_strict

# 전체 감사 결과 JSON 출력
secnorm "аpple.com" --json

# 파이프 입력 (stdin)
cat input.txt | secnorm --preset llm_input_sanitize > output.txt

# 모듈 형태로 직접 실행
python -m secnorm "Hello   world"
```

---

## 결과 직렬화 (Serialization)

```python
# 감사 로그 저장을 위한 직렬화 (dict 및 JSON 지원)
data = result.to_dict()
json_str = result.to_json(indent=2)

# 민감정보(원본 텍스트) 제외 직렬화
sanitized_json = result.to_json(include_raw_text=False)
```

---

## 라이선스

MIT License.
