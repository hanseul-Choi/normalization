# Unicode 정규화 Conformance 검증 리포트

## 한눈에 보기 (TL;DR)

| 항목 | 결과 |
|---|---|
| 검증 대상 | `secnorm.steps.unicode_step` → `unicodedata2`(primary) / `unicodedata`(fallback) |
| 검증 기준 | Unicode 공식 [`NormalizationTest.txt`](https://www.unicode.org/Public/UCD/latest/ucd/NormalizationTest.txt) (UAX #15), 버전 18.0.0 |
| 테스트 라인 수 | 20,171줄 × 2개 백엔드 |
| 실패 건수 | `unicodedata2` 672건 / `unicodedata` 950건 |
| **실패 원인** | **100% Unicode 버전 지연** (라이브러리 테이블 17.0.0·16.0.0 vs 테스트 18.0.0의 신규 할당 코드포인트) — 오탐·알고리즘 버그 **0건** |
| Part1-fill 전수 스윕 (각 백엔드 자체 인지 문자 대상) | 두 백엔드 모두 실패 **0건** |
| v1 지원 언어(ko/en/ja/zh) 영향 | 사실상 없음. 유일하게 스코프 겹치는 건 일본어 세로쓰기 합자 4개(U+1B123~1B126)뿐이며 위험도 낮음 |
| **조치 필요 여부** | **불필요.** `unicodedata2`가 Unicode 18.0 데이터를 배포하면 재검증 권장 (아래 재검증 명령 참고) |

---

- 검증 대상: `secnorm.steps.unicode_step.UnicodeStep` (→ `docs/03-step1-unicode-normalization.md`)이 실제로 호출하는 정규화 백엔드
  - Primary: `unicodedata2` (설치되어 있으면 우선 사용)
  - Fallback: 표준 라이브러리 `unicodedata`
- 검증 기준: Unicode 공식 conformance 테스트 스위트 [`NormalizationTest.txt`](https://www.unicode.org/Public/UCD/latest/ucd/NormalizationTest.txt) (UAX #15)
  - 다운로드 당시 파일 버전: **NormalizationTest-18.0.0.txt** (2026-06-24)
- 검증 스크립트: [`scripts/check_normalization_conformance.py`](../scripts/check_normalization_conformance.py)
- 스크립트 로직 단위 테스트: [`tests/test_normalization_conformance_script.py`](../tests/test_normalization_conformance_script.py) (6개, 모두 통과, `ruff check` 통과)
- 검증 실행일: 2026-09-22

## 검증 방법

`NormalizationTest.txt`의 각 행 `c1;c2;c3;c4;c5`에 대해 UAX #15가 규정한 conformance 불변식을 그대로 구현해 검사했다.

```
NFC:  c2 == NFC(c1) == NFC(c2) == NFC(c3)      c4 == NFC(c4) == NFC(c5)
NFD:  c3 == NFD(c1) == NFD(c2) == NFD(c3)      c5 == NFD(c4) == NFD(c5)
NFKC: c4 == NFKC(c1) == NFKC(c2) == NFKC(c3) == NFKC(c4) == NFKC(c5)
NFKD: c5 == NFKD(c1) == NFKD(c2) == NFKD(c3) == NFKD(c4) == NFKD(c5)
```

추가로 스펙 2번째 규칙("Part 1에 명시적으로 나열되지 않은, 이 구현체 기준으로 할당된 모든 코드포인트 X는 `X == NFC(X) == NFD(X) == NFKC(X) == NFKD(X)`, 즉 정규화에 대해 불변이어야 한다")도 0x0000~0x10FFFF 전체를 스윕하며 각 백엔드 자신의 `category() != "Cn"`(미할당 아님) 기준으로 검사했다.

## 결과 요약

| 백엔드 | 자체 Unicode 버전 | 테스트 라인 | 개별 체크 | 실패(Part0-3) | Part1-fill 체크 | Part1-fill 실패 |
|---|---|---:|---:|---:|---:|---:|
| `unicodedata2` (primary) | 17.0.0 | 20,171 | 403,420 | **672** | 280,248 | **0** |
| `unicodedata` (fallback) | 16.0.0 | 20,171 | 403,420 | **950** | 275,446 | **0** |

## 결론: 실제 정규화 알고리즘 버그 없음 — 전부 Unicode 버전 지연(version skew)

실패한 672건(및 950건)을 전수 조사한 결과, **예외 없이 전부** 테스트 데이터의 c1~c5에 Unicode 18.0.0에서 새로 할당됐지만 해당 백엔드의 테이블(17.0.0 / 16.0.0)에는 아직 없는 "미할당(Cn)" 코드포인트가 포함된 행이었다. 예:

- `0558;0558;0558;0567;0567;` — Unicode 18.0에서 새로 추가된 아르메니아 소문자 호환 매핑. `unicodedata2` 17.0.0 테이블에는 U+0558이 아직 미할당이라 NFKC/NFKD가 항등 변환됨.
- `209D;209D;209D;0077;0077;` (U+209D) 등도 동일하게 18.0.0 신규 할당.
- 결합 문자 재정렬이 얽힌 긴 시퀀스(`0061 0315 0300 05AE 10ECB 0062;...`)들도 모두 시퀀스 중간에 신규 할당 코드포인트(예: U+10ECB, U+1AEC 등)가 하나씩 포함되어 있고, 그 문자가 미할당 취급되면서 결합 클래스(ccc)가 0으로 처리되어 재정렬 결과가 기대값과 달라짐.

반대로 **Part 1 "fill" 체크(자기 자신의 Unicode 버전 기준 할당된, 명시적으로 테스트되지 않은 모든 문자가 정규화에 대해 불변이어야 한다는 규칙)는 두 백엔드 모두 실패 0건**이었다 — 즉 각 백엔드가 스스로 인지하고 있는 문자 집합 내에서는 정규화 알고리즘 구현 자체에 결함이 없다.

**요약**: `secnorm`의 1단계(Unicode 정규화)는 두 백엔드(`unicodedata2`, 표준 `unicodedata`) 모두에서 각자가 지원하는 Unicode 버전 범위 내에서 UAX #15 conformance를 100% 만족한다. 실패는 전부 "테스트 스위트가 검증하는 Unicode 버전(18.0.0)"과 "현재 설치된 라이브러리의 Unicode 데이터 버전(17.0.0 / 16.0.0)" 간의 지연 때문이며, 이는 secnorm 코드의 버그가 아니라 서드파티 라이브러리(`unicodedata2` PyPI 패키지, CPython 내장 `unicodedata`)가 아직 최신 Unicode 버전 데이터를 따라잡지 못한 것이다. `uv.lock`에 고정된 `unicodedata2==17.0.1`이 현재 PyPI에 배포된 최신 버전이라 더 올릴 수 없는 상태였다.

## 권장 조치

- **당장 코드 변경 불필요.** v1 지원 언어(ko/en/ja/zh, `docs/01-overview.md`)와 관련된 코드포인트 범위에서는 이번 스캔에서 아무 문제도 발견되지 않았다.
- `unicodedata2`가 Unicode 18.0.0 데이터를 반영한 새 버전을 PyPI에 배포하면 `uv.lock`을 갱신하고 본 스크립트를 재실행해 회귀가 없는지 재확인할 것을 권장한다.
- 재검증 방법:
  ```bash
  curl -O https://www.unicode.org/Public/UCD/latest/ucd/NormalizationTest.txt
  python scripts/check_normalization_conformance.py NormalizationTest.txt
  ```
