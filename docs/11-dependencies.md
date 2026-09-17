# 11. 의존성 정책

## 원칙 (확정됨)

CPU 기반, `import`로 쓰는 순수 Python 생태계 라이브러리를 우선한다. 가벼운 서드파티는 허용하되, 다음 기준을 만족해야 도입한다.

1. GPU/무거운 ML 모델(transformer 등)을 요구하지 않을 것
2. 순수 Python이거나, 순수 Python 수준으로 가벼운 C 확장(빌드/배포 복잡도 낮음)일 것
3. 활발히 유지보수되고 있고, 유니코드 표준 최신 버전을 반영할 것
4. 없어도 되는데 편의상 넣는 게 아니라, 표준 라이브러리로는 명백히 부족한 지점을 메꿀 것

## 단계별 의존성 표

| 단계 | 표준 라이브러리 | 권장 서드파티 | 서드파티 선택 이유 |
|---|---|---|---|
| 공통 | `dataclasses`, `re`, `typing` | `regex` | 표준 `re`는 유니코드 속성 클래스(`\p{Script=Latin}`, `\X` grapheme cluster)를 지원하지 않음. 5단계(반복문자), 6단계(난독화)에서 필수 |
| 1. Unicode 정규화 | `unicodedata` | `unicodedata2` (선택) | 인터프리터 내장 `unicodedata`가 오래된 Unicode 버전에 고정된 경우 최신 문자 대응 |
| 2. 비가시/제어 문자 | `unicodedata` | — | 코드포인트 범위 테이블은 자체 구현으로 충분, 외부 불필요 |
| 3. 공백 정규화 | `re` | (공통 `regex`) | |
| 4. 인코딩/이스케이프 | `html`, `urllib.parse`, `codecs` | `ftfy` (mojibake 복구, 선택), `charset-normalizer` (bytes 입력 시 인코딩 감지) | 둘 다 순수 CPU, 성숙하고 활발히 유지보수됨. `ftfy`는 이 문제(깨진 인코딩 복구)를 위해 만들어진 사실상 표준 라이브러리 |
| 5. 반복 문자 | (공통 `regex`) | `emoji` (선택, 이모지 범위/시퀀스 데이터) | 이모지 ZWJ 시퀀스 판별을 자체 유지보수하는 대신 최신 이모지 데이터를 받아쓰기 위함. 없어도 grapheme cluster 기반 근사로 동작은 가능 |
| 6. 난독화 정규화 | `re`, `base64` | (공통 `regex`), confusables 데이터는 **정적 파일로 직접 번들** (패키지 의존 아님) | homoglyph 매핑용 서드파티 패키지(`confusable-homoglyphs` 등)는 유지보수가 뜸해서 최신 Unicode 버전 반영이 늦을 위험 → Unicode.org 공식 `confusables.txt`를 라이브러리가 직접 관리하는 쪽이 신뢰성이 높음 |
| 7. 언어/구조 메타데이터 | `re` | `langdetect` (ja/zh 애매 케이스 폴백 전용) | 순수 Python, 외부 API 호출 없음, 가벼움. 대안 `lingua-language-detector`는 정확도는 더 높지만 모델 데이터가 커서(수십MB) "가벼운 의존성" 원칙에 안 맞음 → v1은 `langdetect` 채택, 정확도 이슈가 실제로 발견되면 재검토 |

## 검토했으나 채택하지 않은 것들

| 후보 | 미채택 이유 |
|---|---|
| `spaCy`, `transformers` 기반 언어감지/NER | 무거운 모델, GPU 지향 생태계, "CPU 기반 가벼운 라이브러리" 원칙과 배치 |
| `pydantic` (설정 검증용) | 표준 `dataclasses` + 수동 validation으로 충분한 규모, 무거운 의존성 회피 |
| `confusable-homoglyphs` 패키지 | 데이터 최신성/유지보수 불확실 → 공식 데이터 직접 번들로 대체 |
| `pycld3`/`fasttext` (언어감지) | C++/네이티브 바이너리 빌드 필요, 배포 복잡도 증가. 4개 언어 한정 범위에서는 과함 |

## 라이선스 확인 필요 항목

- Unicode.org `confusables.txt`: Unicode License (재배포 허용, 고지 필요) — 번들 시 라이선스 고지 포함.
- `ftfy`: MIT
- `regex`: Apache 2.0 / CNRI 계열 (확인 필요)
- `langdetect`: Apache 2.0

실제 도입 시 `pyproject.toml`의 optional-dependencies 그룹으로 분리 (`secnorm[full]` 설치 시 `ftfy`, `charset-normalizer`, `langdetect`, `emoji`, `unicodedata2`, `regex` 전부 포함, 기본 설치는 `regex`만 필수로 하고 나머지는 optional — 해당 기능 미사용 시 미설치 상태로도 핵심 파이프라인이 동작해야 함).
