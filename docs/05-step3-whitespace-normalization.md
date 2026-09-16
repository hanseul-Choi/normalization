# 05. 3단계 — Whitespace Normalization

## 목적

공백류 문자의 다양한 변형(전각 공백, NBSP, 각종 폭의 space 등)을 표준화하고, 공백을 이용한 필터 우회(단어 사이 불필요한 공백 삽입 등은 6단계 separator-injection과 겹치므로 이 단계는 "정상적인 공백류 문자의 표준화"에 집중)를 처리한다.

## 대상

Unicode `Zs`(Space Separator), `Zl`(Line Separator), `Zp`(Paragraph Separator) 카테고리 + 자주 악용되는 개별 문자들.

| 문자 | 설명 | 정책 |
|---|---|---|
| `U+0020` | 일반 space | 기준(canonical) 문자 |
| `U+00A0` (NBSP), `U+2007`, `U+202F` | non-breaking space류 | 일반 space로 치환 |
| `U+2000`-`U+200A` (en quad, em space, thin space, hair space 등) | 각종 폭 공백 | 일반 space로 치환 |
| `U+3000` (표의문자 공백, 전각 공백) | 한중일 텍스트에서 문단 들여쓰기 등에 실제 사용됨 | **언어 인지 정책**: 기본은 일반 space로 치환하되, `preserve_ideographic_space=True` 옵션으로 유지 가능 (7단계 언어 감지 결과가 ja/zh일 때만 보존하는 조건부 모드도 지원) |
| `U+2028` (LS), `U+2029` (PS) | 라인/문단 구분자 | `\n`으로 치환 |
| `U+000B`, `U+000C` (수직 탭, 폼 피드) | | `\n` 또는 space로 치환 (설정 가능) |
| `\t` | 탭 | 기본은 space로 치환 (설정으로 유지 가능) |

## 반복/양끝 공백 처리

- 연속된 공백(2개 이상)은 기본적으로 1개로 축약. 단, **개행은 별도 취급**: 문단 구조가 의미 있는 입력(예: 긴 게시글)을 위해 `collapse_newlines` 옵션을 분리 제공.
  - `whitespace_mode="strict"` (기본, 실시간 단건 채팅/짧은 메시지용): 모든 공백류(개행 포함)를 단일 space로 축약. 탐지 목적에서는 구조보다 "정규화된 한 줄"이 유리.
  - `whitespace_mode="structural"` (긴 문서/게시글용): 개행은 최대 2연속(문단 구분)까지 허용하고 그 외 공백만 축약.
- 문자열 앞뒤 공백은 기본 trim.

## 정책 파라미터

```python
@dataclass
class WhitespaceStepConfig:
    mode: Literal["strict", "structural"] = "strict"
    preserve_ideographic_space: bool = False
    tab_policy: Literal["to_space", "keep"] = "to_space"
    trim_edges: bool = True
```

## 플래그

- 이 단계 자체는 대부분 정상적인 변형이므로 기본적으로 플래그를 만들지 않는다.
- 예외: 한 문장 안에서 공백류 문자 종류가 비정상적으로 많이 섞여 있으면(예: 일반 space, NBSP, hair space가 한 단어 내에 번갈아 등장) `SuspicionFlag(category="separator_injection", severity="low")`를 남기고 상세 처리는 6단계로 위임 (공백 자체가 아니라 "공백을 이용한 글자 분리 우회" 패턴이므로 책임은 6단계 문서 참고).

## 구현

- `str.translate()`로 공백류 문자 → canonical 문자 매핑 테이블 적용 (O(n)).
- 연속 공백 축약은 표준 `re` 모듈로 충분 (`re.sub(r' {2,}', ' ', text)` 류). Unicode 공백 속성이 필요한 경우 `regex` 모듈(`\p{Zs}`)을 사용 (`11-dependencies.md`).

## 예시

| 입력 | 출력 |
|---|---|
| `무료   상담  가능` | `무료 상담 가능` |
| `안녕　하세요` (ja/zh 컨텍스트 아님) | `안녕 하세요` |
| `줄바꿈\n\n\n\n많음` (`structural` 모드) | `줄바꿈\n\n많음` |
