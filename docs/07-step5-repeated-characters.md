# 07. 5단계 — Repeated-Character Normalization

## 목적

`coooooool`, `!!!!!!!!!`, `ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ` 처럼 과도하게 반복된 문자를 표준 길이로 축약해서, 반복 횟수만 다른 변형들이 동일한 정규화 결과로 수렴하게 한다 (스팸/강조 우회 탐지에 유용).

## 정책 (확정됨)

**N개까지만 허용하고, 원본 반복 횟수는 메타데이터에 보존한다.** 완전히 1개로 축약하지 않는 이유: `cool`, `쓰레기` 같은 정상 이중 자모/이중 문자를 깨뜨리지 않기 위함. 원본 반복 횟수를 남기는 이유: "몇 번 반복됐는가" 자체가 스팸/강조 탐지에 유용한 신호이기 때문 (완전 손실 압축을 피함).

## 카테고리별 상한 (기본값)

문자 종류에 따라 정상적인 반복 관용구의 빈도가 다르므로 카테고리별로 다른 상한(cap)을 적용한다.

| 카테고리 | 예시 | 기본 상한 (cap) | 근거 |
|---|---|---|---|
| 일반 문자(라틴/한글 음절 등) | `coooool`, `대박박박` | 2 | 정상 영단어의 이중 자모(`cool`, `see`)를 보존하는 최소값 |
| 한글 자모 단독(ㅋㅋㅋ, ㅎㅎㅎ, ㄷㄷㄷ) | `ㅋㅋㅋㅋㅋㅋㅋ` | 3 | 한국어 채팅 관용구는 2개로는 부자연스럽고, 실제 의미 구분(웃음 강도)이 3개 선에서도 어느 정도 보존됨 |
| 구두점/기호 (`!`, `?`, `.`, `~`) | `대박!!!!!!` | 3 | 강조 표현 관용 허용 범위 |
| 이모지 | 😂😂😂😂😂😂 | 3 | 메시지형 플랫폼에서 흔한 강조 패턴 |
| 공백 | (연속 공백) | 이 단계에서 다루지 않음 | 3단계(공백 정규화)의 책임 |

카테고리 판별은 `unicodedata.category()` + 한글 자모 블록(`U+3131`-`U+318E`) 명시적 체크 + 이모지 여부(`emoji` 패키지 데이터 또는 자체 유니코드 범위 테이블)로 수행.

## 정책 파라미터

```python
@dataclass
class RepeatedCharStepConfig:
    default_cap: int = 2
    jamo_cap: int = 3
    punctuation_cap: int = 3
    emoji_cap: int = 3
    min_run_length_to_flag: int = 5   # 이 값 이상 반복되면 플래그 생성
    category_overrides: dict[str, int] = field(default_factory=dict)
```

## 출력

- 각 축약마다 `Transformation(step="repeated_char", rule="collapse_run", metadata={"original_count": N, "collapsed_to": cap, "char": ch})` 기록.
- `original_count >= min_run_length_to_flag`인 경우 `SuspicionFlag(category="excessive_repetition", severity="low")` 생성 (심각도는 낮게 — 그 자체로는 위험 신호라기보단 스팸/도배 탐지용 보조 신호).

## 구현

- `regex` 모듈(또는 표준 `re`)로 run-length 패턴(`(.)\1{N,}`) 탐지 후 카테고리 판별해서 축약. 유니코드 문자 경계(서로게이트 페어, 결합 문자 시퀀스)를 고려해 grapheme cluster 단위로 처리해야 이모지(ZWJ 시퀀스 등)가 깨지지 않음 → `regex` 모듈의 `\X` (grapheme cluster) 사용 권장.

## 예시

| 입력 | 출력 | 메타데이터 |
|---|---|---|
| `coooooool` | `cool` | `{original_count: 7, collapsed_to: 2}` |
| `ㅋㅋㅋㅋㅋㅋㅋㅋㅋㅋ` | `ㅋㅋㅋ` | `{original_count: 10, collapsed_to: 3}` |
| `대박!!!!!!!!` | `대박!!!` | `{original_count: 8, collapsed_to: 3}` |
