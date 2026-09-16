# CLAUDE.md

이 파일은 이 저장소에서 작업하는 Claude(및 다른 세션)를 위한 안내다.

## 프로젝트 상태

기획 완료, 구현 시작 전 단계. 전체 요약은 [`README.md`](./README.md), 상세 설계는 [`docs/`](./docs/)를 참고. 특히 아래 두 문서를 먼저 읽을 것:

- [`docs/01-overview.md`](./docs/01-overview.md) — 목표, 범위, 설계 원칙
- [`docs/13-roadmap.md`](./docs/13-roadmap.md) — 구현 단계(Phase 0~4)와 v1 범위/제외 사항

## 브랜치 전략 (중요)

- `main`이 항상 안정 브랜치. **`main`에 직접 커밋하지 않는다.**
- `docs/13-roadmap.md`에 정의된 Phase(0: 프로젝트 뼈대, 1: 1~4단계, 2: 5·7단계, 3: 6단계 난독화, 4: 통합/품질) **각각을 별도 브랜치로 진행**하고, 완료되면 `main`으로 머지한다.
- 브랜치 네이밍은 로드맵 Phase 번호를 따른다 (예: `phase-0-scaffolding`, `phase-1-core-steps`, `phase-2-heuristics`, `phase-3-obfuscation`, `phase-4-integration`). Phase 내부에서 작업을 더 쪼개야 하면 `phase-1-unicode-step`처럼 세분화해도 되지만, 반드시 어느 Phase에 속하는지 브랜치명에 드러낼 것.
- 새 작업을 시작하기 전 사용자에게 어떤 Phase/브랜치로 진행할지 먼저 확인한다.

## 설계상 반드시 지켜야 할 것 (문서와 충돌 시 문서가 우선, 이 목록은 요약일 뿐)

- 파이프라인은 항상 7단계 순서를 따른다: Unicode → invisible/control → whitespace → encoding/escaping → repeated-char → obfuscation(optional) → language/structural metadata. (`docs/02-architecture.md`)
- 출력은 단순 문자열이 아니라 `NormalizationResult` (정규화 텍스트 + transformations + flags + language metadata + span map). (`docs/02-architecture.md`)
- 6단계(난독화)는 오탐 위험에 따라 canonical text 반영 여부를 구분한다: homoglyph만 canonical 반영, leetspeak/구분자삽입은 `normalized_variants["aggressive"]`에만 반영. (`docs/08-step6-obfuscation-normalization.md`)
- 의존성은 CPU 기반, 표준 라이브러리 우선 + 가벼운 서드파티만 허용 (GPU/무거운 ML 모델 금지). (`docs/11-dependencies.md`)
- v1 지원 언어는 ko/en/ja/zh 4개로 한정. (`docs/01-overview.md`, `docs/09-step7-language-structural-metadata.md`)
- 각 파이프라인 단계는 on/off 가능하고 커스텀 단계를 끼울 수 있어야 한다 (플러그인 구조). (`docs/02-architecture.md`, `docs/10-api-design.md`)

## 작업 시작 시 체크리스트

1. `docs/13-roadmap.md`에서 현재 어느 Phase까지 완료됐는지 확인 (git log/브랜치 히스토리로 판단).
2. 새 Phase 브랜치를 딴다.
3. 해당 Phase에 관련된 `docs/0X-*.md` 문서를 먼저 읽고 구현.
4. 문서와 실제 구현이 달라지면(설계를 바꿔야 하면) 코드만 바꾸지 말고 해당 `docs/*.md`도 함께 갱신한다.
