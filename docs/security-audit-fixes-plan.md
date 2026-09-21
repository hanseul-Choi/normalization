# 보안 감사 발견 사항 수정 계획 (2026-09)

이 문서는 `fix/normalization-security-audit` 브랜치에서 처리할 6건의 보고된 버그 + 조사 중 추가로 발견한 1건(총 7건)에 대한 근본 원인 분석과 구현 계획이다. 로드맵(`docs/13-roadmap.md`)의 Phase 0~13은 이미 전부 완료된 v1 이후 유지보수 작업이므로, 별도 Phase로 편입하지 않고 일반 버그수정 브랜치로 진행한다 (사용자 확인 완료).

> **후속 추가 (2026-09-20)**: A~G(7건)는 `main`에 반영 완료된 뒤, 2단계(invisible/control)의 Variation Selector 처리를 재점검하다 2건(**H**, **I**)을 추가로 발견했다. 두 항목은 `fix/normalization-security-audit-step2-vs` 브랜치에서 처리하며, 이 문서 갱신 시점에는 **문서만 갱신되고 코드는 아직 미구현**이다 (사용자 확인 완료: 문서 선행, 코드/테스트는 별도 작업).

각 항목은 "근본 원인 → 수정 방안 → 변경 파일 → 문서 갱신 → 테스트"로 정리한다. 구현 순서는 [작업 순서](#작업-순서) 참고.

---

## A. (High) `security_strict`가 위험한 URL 디코딩 후 flag를 전부 잃음

**재현**: `secnorm.normalize("%3Cscript%3Ealert(1)%3C/script%3E", preset="security_strict")` → `<script>alert(1)</script>`, `flags=[]`, `score=0.0`, `allow`. `..%2f..%2fetc%2fpasswd`도 동일.

**근본 원인**: `src/secnorm/steps/encoding_escaping_step.py:52-66` `_decode_urls()`가 `mode == "always"`일 때 `unquote(text), []`를 무조건 반환한다. `url_context_only`(기본값, `security_balanced`)에서는 URL 문맥 밖의 `%XX`를 `low` severity `encoded_payload`로 플래그하는 경로가 있지만(검증 완료: `security_balanced`에서는 동일 입력이 `score=0.68`, `action=flag`로 정상 동작), `security_strict`가 켜는 `always` 모드는 이 경로를 아예 타지 않아 디코딩만 하고 어떤 감사 흔적도 남기지 않는다. `docs/06-step4-encoding-escaping.md`는 `url_context_only`의 flag 규칙만 기술하고 `always` 모드의 flag 동작은 명시하지 않은 문서 공백이다.

**수정 방안**: `_decode_urls(text, mode="always")`에서도 `_PERCENT_ENCODED_RE`로 텍스트 전체의 `%XX` 스팬을 찾아 반환하고, 호출부에서 `encoded_payload` / severity `medium` (rule/detail: `percent_encoding_decoded_always_mode`)으로 플래그를 남긴다.

실제 `RiskScorer`로 수치를 검증했다 (재현 문자열의 `%XX` 개수: `<script>...` 예시는 4회, `..%2f..%2fetc%2fpasswd`는 **3회** — 처음 계획 초안에서 2회로 잘못 셌던 것을 바로잡음):

| severity | 3회 (경로 순회) | 4회 (스크립트) |
|---|---|---|
| `low` (0.1×1.2배) | score 0.36 → `flag` | score 0.48 → `flag` |
| `medium` (0.25×1.2배) | score 0.9 → `block` | score 1.0 → `block` |

즉 `low`만 줘도 "`allow`로 새는" 원래 버그 자체는 이미 고쳐진다(둘 다 `flag`로 바뀜). 그럼에도 `medium`을 권장하는 이유는 버그를 고치기 위해 필요해서가 아니라, `security_strict` 프리셋 설명("스팸/우회 탐지 최우선, 오탐 감수")과 정합성을 맞추기 위해서다 — 이 프리셋에서 무조건 디코딩(`always`)까지 켠 상황에서 나온 percent-encoding 뭉치는 대부분 실제 우회 시도이므로 `flag`보다 `block`이 프리셋 취지에 더 맞는다는 판단. 이 부분은 오탐 감수 성향이 강한 판단이라 구현 시 기존 108+개 회귀 테스트를 돌려보고 필요하면 `low`로 낮출 수 있다 ([열린 질문](#열린-질문) 참고).
- `url_context_only` 모드 자체는 이미 올바르게 동작하므로 변경하지 않는다.
- 이 수정은 "디코딩 스킴 자체에 대한 flag"이지 "디코딩된 내용이 `<script>`인지/경로 순회인지"를 패턴 매칭하는 것은 아니다. `docs/06-step4-encoding-escaping.md:5`가 "표준 인코딩 스킴을 정확히 따르는 디코딩"과 "페이로드 내용 탐지"의 경계를 6단계/플러그인 책임으로 명확히 구분하고 있으므로, 이 경계를 지키기 위해 콘텐츠 패턴 매칭(스크립트 태그, `../` 등)은 이번 수정 범위에 넣지 않는다. (콘텐츠 패턴 탐지가 필요하면 `RegexGuardrailStep`을 조합해 쓰는 것이 기존 설계 의도.)

**변경 파일**: `src/secnorm/steps/encoding_escaping_step.py` (`_decode_urls`, `EncodingEscapingStep.apply`의 URL 디코딩 분기).

**문서 갱신**: `docs/06-step4-encoding-escaping.md` 4-2절에 `always` 모드의 flag 규칙 명시 (예시 표에 `always` 모드 행 추가).

**테스트**: `tests/`에 `security_strict`로 스크립트 태그/경로 순회 percent-encoding 입력 시 `flags`가 비어있지 않고 `evaluate_risk().action != "allow"`임을 확인하는 회귀 테스트 추가. 기존 `security_strict` 관련 테스트(어드버서리얼 코퍼스 포함)에 flag 개수/스코어가 바뀌는 케이스가 있는지 전체 재실행해서 스냅샷성 실패를 점검.

---

## B. (High) 정규화가 멱등적이지 않음 (`normalize(normalize(x)) != normalize(x)`)

**재현**:
- `"hello​world"`(리터럴 백슬래시 문자열) 1회 정규화 → `"hello​world"`(진짜 ZWSP 문자 생성, flag는 `encoded_payload`만). 2회째 정규화에서야 `zero_width_injection` flag와 함께 제거됨.
- `"%253Cscript%253E"`(이중 URL 인코딩) → 1회당 한 단계씩만 풀림 (`%3Cscript%3E` → `<script>`).

**근본 원인**: 파이프라인 순서가 `Unicode → invisible/control(2단계) → whitespace(3단계) → encoding/escaping(4단계) → ...`으로 고정되어 있다 (`src/secnorm/presets.py:_build_full_steps`). 4단계에서 유니코드 이스케이프/URL 퍼센트 인코딩을 디코딩하면 실제 제어/비가시 문자나 재인코딩된 시퀀스가 "새로" 생성될 수 있는데, 이를 다시 걸러줄 2단계(비가시 문자 제거)나 4단계 자기 자신(재귀 디코딩)이 같은 실행 안에서 다시 돌지 않는다. 결과적으로 한 번의 `normalize()` 호출 뒤에도 텍스트에 위험 신호가 남아있고, 이 잔여물은 다음 번 호출에서야 처리된다 — 보안 정규화가 지향해야 할 "출력에는 더 이상 디코딩/제거할 것이 없어야 한다"는 성질(fixpoint)이 깨져 있다.

**설계 결정 (사용자 확인 완료)**: 전체 5개 프리셋이 아니라 **보안 지향 프리셋(`security_strict`, `security_balanced`, `llm_input_sanitize`)에만** 이 보장을 적용한다. `minimal`/`nlp_preprocessing`은 애초에 위험한 디코딩을 하지 않는(또는 안 하는 것이 정책인) 프리셋이라 비용 대비 이득이 없다.

**수정 방안 — 파이프라인 레벨 fixpoint 재실행**:
1. `NormalizationConfig`(`src/secnorm/config.py`)에 `stabilize_output: bool = False`, `max_stabilize_iterations: int = 3` 필드 추가. `to_dict`/`from_dict`에도 반영.
2. `src/secnorm/presets.py`의 `security_strict`, `security_balanced`, `llm_input_sanitize` 빌더에서 `config.stabilize_output = True` 설정.
3. `src/secnorm/pipeline.py`의 `NormalizationPipeline.run()`을 리팩터링:
   - 현재 로직을 `_run_single_pass(self, text: str) -> NormalizationResult`로 추출 (거의 그대로, `raw_text=text`로 그 호출의 로컬 raw 취급).
   - `run()`은 `_run_single_pass(text)`를 1회 실행한 뒤, `config.stabilize_output`이 꺼져 있으면 그대로 반환.
   - 켜져 있으면: `cur_text = result.normalized_text`가 이전 반복의 입력과 달라지는 동안(즉 안정화될 때까지), 그리고 `max_stabilize_iterations` 한도 내에서 `_run_single_pass(cur_text)`를 반복 실행.
   - **누적 방법**: 매 반복의 `flags`는 그 반복에서 방금 만든 span_map(=이번 반복만의 raw→output 매핑, 여기서 "raw"는 이전 반복의 출력 텍스트)을 기준으로 계산되어 있으므로, 최종 사용자 관점의 원문(raw_text) 좌표로 다시 매핑해야 한다. 지금까지 누적된 `combined_span_map`(원문→직전 반복 출력)에 대해 `combined_span_map.to_raw(flag.span)`을 호출해 좌표를 변환한다. `Transformation.span_before/after`는 설계상 이미 "그 스텝의 입력/출력 기준 좌표"이므로(전역 raw_text 기준이 아님, `encoding_escaping_step.py` 상단 주석 참고) 변환 없이 그대로 이어 붙이면 된다. 다만 `metadata`에 `{"stabilize_iteration": n}`을 추가해 어느 반복에서 나온 변환/플래그인지 감사 가능하게 남긴다.
   - `combined_span_map`은 `diffutil.diff_edits(prev_text, cur_result.normalized_text)`로 얻은 edit 목록을 기존 `combined_span_map.compose(edits)`에 넘겨 갱신한다 (per-step 합성과 동일한 패턴을 반복 단위로 재사용).
   - `normalized_variants`는 마지막 반복 것으로 덮어쓰기(dict update)한다.
   - 루프 종료 조건: `cur_text == prev_text`(완전히 안정화) 또는 반복 횟수 도달. 횟수 도달 후에도 텍스트가 계속 바뀌는 극단적 케이스는 그대로 반환하되, 이후 CLI/HTTP 등에는 영향 없음 (무한루프 방지가 우선).
4. 성능: 보안 프리셋은 기본적으로 최대 3회까지 파이프라인 전체를 다시 돌 수 있으므로 벤치마크(`tests/`의 `pytest-benchmark` 스위트)에서 `security_strict`/`security_balanced`/`llm_input_sanitize` 지연시간이 크게 늘지 않는지 확인 필요. 대부분의 정상 입력은 1회차에서 텍스트가 변하지 않으므로 실질적으로 반복이 발생하지 않는다(비교 `cur_text != prev_text`가 즉시 False).

**사전 검증**: 위 좌표 변환 로직(`combined_span_map.to_raw(flag.span)` → 원문 좌표, 그다음 `combined_span_map.compose(diff_edits(...))`로 갱신)이 실제로 맞물리는지, 이번 계획을 쓰면서 `hello​world` 재현 케이스로 `SpanMap`/`diff_edits`를 직접 조합해 수동 시뮬레이션했다: 1회차 결과(`raw→mid` span_map)를 이용해 2회차에서 나온 `zero_width_injection` 플래그의 스팬(`mid` 좌표 `Span(5,6)`)을 원문 좌표로 되돌렸더니 정확히 `Span(5,11)`(원문의 리터럴 `​` 6글자 구간)로 매핑됐다. 알고리즘 자체는 검증됐고, 실제 구현은 이를 `run()` 루프 안에 넣는 리팩터링 작업이다.

**변경 파일**: `src/secnorm/config.py`, `src/secnorm/pipeline.py`, `src/secnorm/presets.py`.

**문서 갱신**: `docs/02-architecture.md`에 "정규화는 결정적이다" 항목 옆에 "보안 프리셋은 추가로 fixpoint(최대 N회 재실행)까지 보장한다" 명시. `docs/10-api-design.md`의 프리셋 표에도 `stabilize_output` on/off 여부 추가.

**테스트**: `normalize(normalize(x)) == normalize(x)`를 보안 3개 프리셋에 대해 검증하는 hypothesis 기반 속성 테스트 추가 (`tests/`의 기존 property-based 테스트 파일에 케이스 추가). 최소한 이번에 보고된 두 재현 케이스(`​` 리터럴, 이중 URL 인코딩)를 유닛 테스트로 고정.

---

## C. (High) HTTP `/normalize/batch`가 타입 검증 누락으로 연결이 끊김

**재현**: `{"texts": ["ok", 123]}` POST 시 400이 아니라 커넥션이 끊기고 서버 stderr에 traceback 발생 (서버 프로세스 자체는 생존).

**근본 원인**: `src/secnorm/server.py:78-80`에서 `texts`가 `list`인지만 검사하고 원소 타입은 검사하지 않는다. `secnorm.normalize_batch(texts, ...)` 내부에서 정수 `123`에 대해 문자열 전용 연산(정규식 등)을 수행하다 `TypeError`(또는 유사 예외)가 발생하는데, `do_POST`는 `except ValueError`만 잡으므로 이 예외가 그대로 전파된다. `BaseHTTPRequestHandler`는 핸들러 밖으로 예외가 나가면 (이미 응답 헤더를 안 보낸 상태이므로) 클라이언트에 아무 응답도 못 보내고 연결만 닫는다 — 스레드/프로세스 자체는 죽지 않아 "서버는 살아있는데 그 요청만 응답 없음"이라는 보고 내용과 정확히 일치.

**수정 방안**:
1. `/normalize/batch` 입력 검증 강화: `texts`의 모든 원소가 `str`인지 확인, 아니면 400.
   ```python
   if texts is None or not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
       self._send_error(400, "'texts' field is required and must be a list of strings")
       return
   ```
2. `n_jobs` 필드도 실제로 같은 방식으로 재현 확인함: `secnorm.normalize_batch(["a","b"], n_jobs="not-an-int")` → `TypeError: '<=' not supported between instances of 'str' and 'int'`가 그대로 전파되어 동일하게 연결이 끊긴다. `n_jobs`가 `int`인지(및 `>= 1`인지) 검증해 아니면 400을 반환하도록 확정 수정 대상에 포함한다.
   - 참고로 `preset` 필드는 이미 안전함을 확인했다: `secnorm.normalize(text, preset=123)` / `normalize_batch(texts, preset=None)` 둘 다 `ValueError("unknown preset: ...")`를 던지고 서버가 이미 `except ValueError`로 잡고 있어 400으로 정상 응답한다. `include_raw_text`/`include_risk`도 `bool()` 캐스팅 없이 그냥 `to_dict()`에 전달되는 값이라 타입이 달라도 예외를 던지지 않는 값(truthy/falsy 판정만)이라 크래시 경로는 아니다 — 다만 오동작(예: `"false"` 문자열이 truthy로 처리됨) 가능성은 있으니 구현 시 한 번 더 확인.
3. 방어적으로 `do_POST`의 각 엔드포인트 처리 블록에서 `except ValueError`를 `except (ValueError, TypeError)`로 넓히거나, 최상위에 `except Exception as e: self._send_error(400, ...)` 형태의 캐치올을 추가해 앞으로 비슷한 유형의 미검증 입력이 서버 프로세스 응답 불능으로 이어지지 않게 한다 (개별 필드 검증은 1./2.로 명시적으로 처리하고, 이 캐치올은 "미처 못 막은 나머지"에 대한 안전망). 다만 어떤 예외까지 400으로 뭉뚱그릴지(vs. 500으로 구분)는 아래 [열린 질문](#열린-질문) 참고.

**변경 파일**: `src/secnorm/server.py`.

**문서 갱신**: `docs/10-api-design.md`의 HTTP API 절에 `/normalize/batch` 입력 검증 규칙(모든 원소가 string이어야 함) 명시.

**테스트**: `tests/test_http_server.py`에 `{"texts": ["ok", 123]}`, `{"texts": [None]}`, `{"texts": "not-a-list"}`, `{"texts": ["ok"], "n_jobs": "not-an-int"}` 등에 대해 연결이 유지된 채 400이 반환되는지 확인하는 테스트 추가. 서버가 다음 요청도 정상 처리하는지(프로세스 생존 확인)까지 같은 테스트에서 검증.

---

## D. (Medium) HTML entity 디코딩이 활성 마크업을 드러내는데 위험도는 safe

**재현**: `"&lt;script&gt;alert(1)&lt;/script&gt;"` → `"<script>alert(1)</script>"`, `flags=[]`, `score=0.0`.

**문서와의 관계**: `docs/06-step4-encoding-escaping.md:13`은 "디코딩 후 결과에 다시 `<`, `>` 등 HTML 특수문자가 생기면 → 이 자체는 정상(사용자가 HTML entity로 인코딩된 코드 스니펫을 붙여넣었을 수 있음), 플래그는 만들지 않음"이라고 **명시적으로 규정**하고 있다. 즉 지금 동작은 버그가 아니라 문서화된 설계다. 다만 "정규화 결과를 그대로 HTML에 삽입하는 소비자" 관점에서는 이 설계가 위험하므로, 프리셋별로 위험 감수 수준이 다르다는 점을 활용해 정책을 분기한다.

**설계 변경 (사용자 확인 완료)**: `security_balanced`/`nlp_preprocessing`/`minimal`은 문서의 기존 방침을 그대로 유지(flag 없음, 오탐 방지 우선). **`security_strict`, `llm_input_sanitize` 두 프리셋만** HTML entity 디코딩 결과에 활성 마크업이 나타나면 새 카테고리 `decoded_markup`(severity `medium`)을 플래그한다.

**수정 방안**:
1. `EncodingEscapingStepConfig`(`src/secnorm/config.py`)에 `flag_decoded_markup: bool = False` 추가.
2. `src/secnorm/steps/encoding_escaping_step.py`의 HTML entity 디코딩 분기를 다음과 같이 바꾼다: `record_changes`를 바로 호출하는 대신, `cfg.flag_decoded_markup`이 켜져 있을 때는 먼저 `decoded = html.unescape(current)`를 계산하고 `_, changes = diff_edits(current, decoded)`로 각 변경 구간의 `replacement` 문자열만 따로 뽑아, 그중 태그 시작처럼 보이는 저비용 정규식(`<[a-zA-Z/!]`)에 매칭되는 구간만 `record_flags(...)`로 `decoded_markup`/`medium` 플래그를 남긴 뒤 `record_changes(decoded, "decode_html_entity")`를 호출한다. 이렇게 "이번 엔티티 디코딩이 실제로 만들어낸 구간"만 정확히 짚어야, 애초에 유저가 리터럴 `<script>`를 이미 입력해뒀던 경우(엔티티 디코딩과 무관)까지 잘못 플래그하지 않는다. (완전한 HTML 파서를 쓰지 않고 태그 시작처럼 보이는 패턴만 저비용으로 검사 — 남은 오탐/누락 감수는 문서에 명시.)
3. `src/secnorm/presets.py`: `security_strict`, `llm_input_sanitize` 빌더에서 `config.encoding_escaping.flag_decoded_markup = True`.

**변경 파일**: `src/secnorm/config.py`, `src/secnorm/steps/encoding_escaping_step.py`, `src/secnorm/presets.py`.

**문서 갱신**: `docs/06-step4-encoding-escaping.md` 4-1절에 "단, `security_strict`/`llm_input_sanitize`는 예외적으로 `decoded_markup` 플래그를 남긴다"는 예외 조항 추가. 예시 표에도 프리셋별 결과 분기를 표시.

**테스트**: `security_strict`/`llm_input_sanitize`에서 HTML entity로 인코딩된 스크립트 태그가 flag를 발생시키는지, `security_balanced`/`nlp_preprocessing`/`minimal`에서는 기존처럼 flag가 없는지(회귀 방지) 둘 다 테스트.

---

## E. (Medium) 이모지 ZWJ가 공격으로 오인되어 의미가 손상됨

**재현**: `"👩🏽‍💻"`(여성 + 피부톤 수정자 + ZWJ + 노트북 = "여성 기술자" 이모지) → `"👩🏽💻"`(ZWJ 제거로 합쳐진 이모지가 깨짐), `zero_width_injection` flag 발생. `nlp_preprocessing`에서 재현했지만 `strip_zero_width=True`가 기본값인 모든 프리셋(`security_balanced`, `security_strict`, `llm_input_sanitize`, `nlp_preprocessing`)에서 동일하게 발생.

**근본 원인**: `src/secnorm/steps/invisible_control_step.py:29` `_ZERO_WIDTH`에 U+200D(ZWJ)가 다른 zero-width 문자와 동일하게 취급되어, 문맥과 무관하게 항상 strip 대상이 된다. `docs/04-step2-invisible-control-chars.md:14`는 "ZWNJ/ZWJ가 실제 서체 결합에 쓰이는 언어 문맥(아랍어 등)"에 대한 예외 여지는 언급하지만 이모지 ZWJ 시퀀스(UTS #51)는 언급하지 않는다.

**설계 결정 (사용자 확인 완료)**: 전체 프리셋에 적용. ZWJ가 emoji-ish 문자(유니코드 `So` 카테고리, 또는 피부톤 수정자 `U+1F3FB`-`U+1F3FF`, 지역표시 문자 등 emoji_presentation 문자) 사이에 있을 때만 보존 예외를 두고, 그 외 위치(일반 텍스트 사이에 숨겨진 ZWJ 스머글링)에서는 기존처럼 계속 제거한다. 이모지 인접 여부만 보고 판단하므로 보안 저하가 아니라 순수 정확도 개선으로 본다.

**수정 방안**: `_classify()`(`src/secnorm/steps/invisible_control_step.py:54`)의 ZWJ 분기에서, 이미 있는 `_is_emoji_ish(prev)` 헬퍼(현재 variation selector 판단에 쓰이는 것, line 50)를 재사용해 `prev`와 `next`(다음 문자) 둘 다 emoji-ish일 때만 `None`(보존)을 반환하도록 예외를 추가한다. `_classify`는 현재 `next` 문자를 인자로 받지 않으므로 시그니처에 `nxt: str | None`을 추가하고 호출부(`InvisibleControlStep.apply`의 루프)에서 `text[i+1] if i+1 < len(text) else None`을 넘긴다.

실제 문자 카테고리를 확인해보니 (`unicodedata.category`) 단순히 `prev`/`next` 한 글자만 보는 걸로는 부족한 두 가지가 드러났다 — 둘 다 구현 시 반드시 반영해야 함:

1. **피부톤 수정자가 `So`가 아니라 `Sk`다.** `U+1F3FB`-`U+1F3FF`(`EMOJI MODIFIER FITZPATRICK...`)는 `unicodedata.category`가 `"Sk"`이지 `"So"`가 아니다. 그래서 "👩🏽‍💻"(WOMAN `So` + 피부톤 `Sk` + ZWJ + LAPTOP `So`)에서 ZWJ 바로 앞 문자는 피부톤 수정자(`Sk`)인데, `_is_emoji_ish`가 `"So"`만 체크하면 이 경우를 놓친다. `_is_emoji_ish`가 `{"So", "Sk"}`를 모두 emoji-ish로 인정하도록 확장 필요.
2. **변형 선택자(VS16 등)가 ZWJ 바로 앞/뒤에 끼는 시퀀스가 실제로 흔하다.** 예: `✍️‍♀️`(WRITING HAND `U+270D` + VS16 `U+FE0F` + ZWJ + FEMALE SIGN `U+2642`)에서 ZWJ 바로 앞 문자는 VS16인데, VS16의 category는 `"Mn"`이라 emoji-ish 판정에 걸리지 않는다. 단순히 `text[i-1]`/`text[i+1]`만 보면 이런 시퀀스는 여전히 깨진다. 따라서 ZWJ 인접성 판단 시, 이 파일에 이미 정의된 `_VS_RANGE`/`_VS_SUPPLEMENT_RANGE`에 속하는 변형 선택자를 건너뛰고 그다음의 실제 base 문자를 찾아 emoji-ish 여부를 판정하는 작은 helper(`_skip_vs_backward(text, i)` / `_skip_vs_forward(text, i)` 형태)가 필요하다.

이 두 가지를 놓치면 "고친 줄 알았는데 VS16 낀 이모지는 여전히 깨지는" 부분 수정이 되므로, 구현 후 최소 3종 시퀀스(피부톤+ZWJ+직업, VS16+ZWJ+성별기호, 가족 이모지처럼 VS 없이 So만 연속)로 왕복 테스트를 반드시 포함한다.

**변경 파일**: `src/secnorm/steps/invisible_control_step.py`.

**문서 갱신**: `docs/04-step2-invisible-control-chars.md` 표에 "이모지 ZWJ 시퀀스(emoji-ish 문자 사이의 U+200D)는 예외적으로 보존" 조항 추가.

**테스트**: 대표적인 ZWJ 이모지 시퀀스(가족 이모지, 피부톤+직업 이모지, 깃발 시퀀스 등) 왕복 보존 테스트 + "일반 텍스트 사이 ZWJ 스머글링은 여전히 제거/플래그된다"는 회귀 테스트(예: `"pass‍word"` 같은 케이스가 계속 strip되는지) 둘 다 추가.

---

## F. (Low) `minimal` 프리셋에서 공백 전용 입력이 빈 문자열로 트림되지 않음

**재현**: `" \t\r\n "` → `"\r"` (기대값: `""`).

**근본 원인**: `src/secnorm/steps/whitespace_step.py`가 CR(`\r`, U+000D)을 전혀 다루지 않는다. `_TO_SPACE_CODEPOINTS`/`_TO_NEWLINE_CODEPOINTS`(line 35-36) 어디에도 `0x0D`가 없어 변환 테이블을 거쳐도 `\r`는 그대로 남고, `_STRICT_COLLAPSE_RE = r"[ \n]+"`(line 40)도 `\r`를 매치하지 않으며, `_TRIM_CHARS = " \t\n"`(line 43)도 `\r`를 포함하지 않는다. 그 결과 `" \t\r\n "` → 변환 후 `" \r\n "`형태 → collapse로 좌우 공백/개행만 뭉개짐 → 좌우 trim에서 `\r` 앞뒤로 trim이 멈춰 `"\r"`만 남는다.

**수정 방안 (초안을 자체 검증 중 수정함)**: 처음에는 `_TO_NEWLINE_CODEPOINTS`에 `0x0D`를 추가해 `str.translate()` 테이블에서 CR→LF로 바꾸는 방식을 생각했으나, 이는 **CRLF(`\r\n`) 텍스트를 실제로 돌려보니 회귀를 만든다**: `translate()`는 문자 단위 1:1 치환이라 `\r\n` 두 글자가 각각 `\n`, `\n`으로 바뀌어 `\n\n`(개행 2개)이 되어버린다. `minimal` 프리셋(strict 모드, `[ \n]+`를 무조건 공백 1개로 뭉갬)은 우연히 영향이 없지만, `structural` 모드(`nlp_preprocessing` 등)는 "빈 줄 하나(개행 2개 이상)=단락 구분"을 구분하는 로직이라 **CRLF로 줄바꿈된 텍스트에서는 단순 줄바꿈까지 전부 단락 구분으로 오인**하게 된다 (`"line1\r\nline2\r\n\r\nline3"`가 원래는 "line1/line2 같은 문단, line3는 다음 문단"이어야 하는데, translate 방식으로는 세 줄이 전부 다른 문단으로 벌어짐 — 실제 시뮬레이션으로 확인).

대신 표준적인 universal-newline 방식으로 **CRLF를 먼저 한 덩어리로 LF로 치환하고, 그다음 남은 단독 CR(구 Mac 스타일)을 LF로 치환**한다 (`text.translate()` 이전에 수행):
```python
text = text.replace("\r\n", "\n").replace("\r", "\n")
```
이렇게 하면 `\r\n` 한 쌍이 정확히 `\n` 한 글자가 되어 기존 collapse/trim 로직이 손대지 않아도 올바르게 동작한다 (`" \t\r\n "` → `" \t\n "` → 이후 기존 로직 그대로 → `""`; CRLF 텍스트의 단락 구분도 보존됨을 실제 코드로 재현·검증 완료).

**변경 파일**: `src/secnorm/steps/whitespace_step.py` (`WhitespaceStep.apply` 최상단, `cfg.mode`/`cfg.tab_policy` 분기보다 먼저 실행).

**문서 갱신**: `docs/05-step3-whitespace-normalization.md`에 "CRLF/CR은 전처리 단계에서 LF로 정규화된다(단락 구분에 영향 없음)"는 조항 추가.

**테스트**: `" \t\r\n "` → `""`(`minimal`), CRLF 텍스트(`"line1\r\nline2\r\n\r\nline3"`)가 `nlp_preprocessing`(structural 모드)에서 line1/line2가 같은 문단으로, line3가 다음 문단으로 유지되는지(즉 위에서 발견한 회귀가 재발하지 않는지) 확인하는 테스트를 반드시 포함.

---

## G. (추가 발견, High) `decode_and_recurse`가 항상 조용히 실패함

이번 조사 중 A 문제를 파다가 발견한, 사용자가 보고하지 않은 별도 버그. 심각도가 높고 A/B 문제와 같은 "디코딩 후 신호 소실" 계열이라 같은 브랜치에서 함께 고친다.

**재현**:
```python
secnorm.normalize("aGVsbG8gPHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==", preset="security_strict")
# flags=[<base64_payload 1건>], score=0.3 — 재귀 디코딩 결과에서 나와야 할 추가 flag가 전혀 없음
```

**근본 원인**: `src/secnorm/steps/obfuscation_step.py:250`에서 `NormalizationConfig()`를 참조하는데, 이 모듈은 파일 최상단에서 `NormalizationConfig`를 import하지 않는다(`from ..config import ObfuscationStepConfig`만 있음, `grep` 결과 `NormalizationConfig`는 파일 어디에도 import돼 있지 않음). 따라서 `cfg.decode_and_recurse=True`인 모든 경우(즉 `security_strict` 프리셋 전체) `NameError`가 발생하고, 이를 감싸는 `except Exception: pass`(line 270)가 조용히 삼켜버려 base64 재귀 정규화가 **한 번도 실행되지 않는다**. `docs/08-step6-obfuscation-normalization.md:39`가 요구하는 "디코딩 성공 + 유효 UTF-8이면 파이프라인 재귀 실행" 기능이 사실상 죽어있는 상태.

**수정 방안**: `from ..config import NormalizationConfig, ObfuscationStepConfig`로 import를 고치는 것이 최소 수정이다. 다만 이 김에 코드 구조도 점검:
- `except Exception: pass`가 `NameError`류의 진짜 버그까지 삼켜버려 이번처럼 기능 전체가 죽어도 어떤 테스트도 잡지 못했다. 최소한 base64 디코딩 자체의 실패(`binascii.Error`, `UnicodeDecodeError`)만 좁게 잡고, 그 외 예외(`NameError`, `AttributeError` 등 프로그래밍 오류)는 전파되게 하거나 로그를 남기는 편이 안전하다. (총점검 시 이런 "과도하게 넓은 except가 진짜 버그를 숨기는" 패턴이 다른 곳에도 있는지 함께 확인 — `encoding_escaping_step.py`의 `ftfy` import 예외 처리 등은 의도된 것이라 문제 없음.)
- 재귀 시 매번 `build_preset("security_balanced")`를 새로 만드는데(line 256), 이는 항상 `security_balanced`로 고정되어 있어 `security_strict`에서 재귀할 때도 재귀 depth에서는 다른(더 약한) 정책이 적용된다. 의도적인지 실수인지 문서(`docs/08-step6-obfuscation-normalization.md`)에 명시가 없어 구현 시 확인 필요 — 일단 이번 수정 범위에서는 "재귀가 실행되긴 하게" 만드는 것까지만 하고, 재귀 시 사용할 프리셋 정책은 별도 이슈로 분리할지 [열린 질문](#열린-질문)에 남긴다.

**변경 파일**: `src/secnorm/steps/obfuscation_step.py`.

**문서 갱신**: 필요시 `docs/08-step6-obfuscation-normalization.md`에 재귀 시 사용하는 하위 프리셋 정책 명시.

**테스트**: base64/hex로 인코딩된 위험 패턴(예: 유니코드 이스케이프나 태그 문자를 담은 base64)이 `security_strict`에서 재귀 디코딩되어 그 안의 flag까지 최종 결과에 나타나는지 확인하는 테스트 추가. `decode_and_recurse=True`가 예외로 죽지 않는지 자체를 검증하는 테스트도 추가(이번처럼 조용히 실패하는 회귀를 막기 위함).

---

## H. (Medium, 후속 추가) 일본어 IVS가 스테가노그래피로 오탐되어 제거됨

**재현** (`secnorm.normalize(...)`, 2단계 결과만 발췌):

| 입력 | 결과 |
|---|---|
| `"葛\U000E0100"` (葛 + IVS `U+E0100`) | VS 제거 + `high` `tag_char_smuggling` 플래그 |
| `"\U0001F600\U000E0100"` (😀 + VS supplement) | VS 제거 + `high` 플래그 (이쪽은 의도된 동작) |
| `"字︀"` (字 + `U+FE00`) | VS 제거 + `high` 플래그 |

**근본 원인**: `src/secnorm/steps/invisible_control_step.py`의 `_classify()`는 VS supplement(`U+E0100`-`U+E01EF`)를 문맥과 무관하게 무조건 `strip` + `high`로 처리한다 (`cp in _VS_SUPPLEMENT_RANGE` 분기). 그런데 이 블록은 **IVS(Ideographic Variation Sequence, 이체자 선택자)**의 정식 코드포인트 범위이기도 하다. IVS는 한자 이체자(예: 葛城의 `葛` 이체자)를 구분하는 표준 메커니즘으로, 일본어 인명·지명 표기(주민 정보, 고객명 등)에 실제로 쓰인다. v1 지원 언어에 `ja`가 포함돼 있으므로 정상 일본어 입력이 `high` 위험으로 표시되는 오탐이 발생한다. `docs/04-step2-invisible-control-chars.md`의 VS 행은 "VS supplement 블록은 제거 + `high`"로만 적혀 있어 IVS 사용 사례가 문서에서도 누락돼 있었다.

**설계 결정 (사용자 확인 완료)**: **CJK 한자 뒤의 VS supplement 1개는 허용**한다.
- 허용 조건 (모두 만족해야 함):
  1. 바로 앞 문자가 CJK 한자(CJK Unified Ideographs 및 Extension A~ 계열: `U+3400`-`U+4DBF`, `U+4E00`-`U+9FFF`, `U+20000`-`U+323AF` 등)이고
  2. 그 뒤의 VS supplement가 **정확히 1개**이며 (다음 문자가 또 VS 계열이 아님)
  3. `strip_variation_selectors != "all"` 인 경우.
- 허용 시 그대로 유지하며 **플래그도 남기지 않는다.**
- 조건을 하나라도 어기면(2개 이상 연속, 한자가 아닌 문자 뒤, 문자열 맨 앞 등) **기존처럼 연속 구간 전체를 제거하고 `high` 플래그**를 남긴다. 연속 VS supplement를 이용한 바이트 인코딩 방식의 스테가노그래피(알려진 공격 형태)는 계속 차단된다.
- `strip_variation_selectors="all"`이면 IVS도 제거한다 (엄격 모드 유지 수단).
- 일반 VS(`U+FE00`-`U+FE0F`)를 한자 뒤에서 허용할지는 이번 결정 범위 밖이다 ([열린 질문](#열린-질문) 참고). 현재 동작(제거 + `high`)을 유지한다.

**잔여 위험 (문서에 명시해 둘 것)**: 이 정책은 "한자 뒤 1개"만 보고 IVD(Ideographic Variation Database)에 등록된 실제 조합인지는 검증하지 않는다. 따라서 **한자마다 VS supplement를 1개씩 붙여 문장 전체에 분산시키는 방식**(한자 1글자당 최대 log2(240) ≈ 7.9bit)은 이 규칙으로는 탐지되지 않는다. 연속 VS를 쓰는 기존 공격 형태는 막히지만, 분산형 변형은 남는다. 완화안은 [열린 질문](#열린-질문)에 남긴다.

**수정 방안**:
1. `_classify()`의 VS supplement 분기에서, 위 허용 조건을 만족하면 `None`(유지)을 반환하는 예외를 추가한다. 앞 문자 조회는 이미 있는 `_skip_vs_backward`를 쓰지 말고(연속 VS를 건너뛰어 버려 "정확히 1개" 판정이 깨짐) `prev`(바로 앞 문자)로 직접 판정하고, "다음 문자가 VS 계열이 아님"은 `text[index + 1]` 조회로 확인한다. `_classify`는 현재 다음 문자를 받지 않으므로 E에서 필요했던 것과 같은 방식으로 `text`/`index`를 이용한다(이미 `text` 인자가 있음).
2. CJK 한자 판정용 코드포인트 범위 상수(`_CJK_IDEOGRAPH_RANGES`)를 같은 파일에 하드코딩 테이블로 추가한다. 별도 의존성은 쓰지 않는다 (`docs/11-dependencies.md`, `docs/04` "구현" 절의 기존 방침과 동일).
3. 허용된 IVS는 변환/플래그를 남기지 않는다. 제거되는 쪽은 기존 `strip_variation_selector` rule과 `tag_char_smuggling` 카테고리를 그대로 쓴다 (플래그 카테고리 체계 변경 없음).

**변경 파일**: `src/secnorm/steps/invisible_control_step.py`.

**문서 갱신**: `docs/04-step2-invisible-control-chars.md`의 Variation Selector 행에 IVS 예외 조항과 잔여 위험 추가. "구현 노트"에도 `_is_emoji_ish`/`_CJK_IDEOGRAPH_RANGES`의 역할 구분을 기록.

**테스트**: 다음을 `tests/test_invisible_control_step.py`에 추가.
- 한자 + IVS 1개 → 유지, 플래그 없음 (`ja` 입력 대표 케이스, 예: `葛\U000E0100城`).
- 한자 + IVS 2개 이상 연속 → 전체 제거 + `high` 플래그.
- 이모지/영문자/문자열 맨 앞의 VS supplement → 기존처럼 제거 + `high` (회귀 방지).
- `strip_variation_selectors="all"`이면 한자 뒤 IVS도 제거.
- `strip_variation_selectors="none"`이면 변화 없음.
- 한자 + IVS + ZWSP 등 다른 스머글링 문자가 섞여도 IVS 판정이 그 문자에 영향받지 않는지.

---

## I. (Low, 후속 추가) `Sk` 카테고리 확장으로 `^`/`` ` `` 뒤의 VS가 통과함

**재현**: `secnorm.normalize("^️")` → 출력 `"^️"` (VS 유지), 2단계 변환/플래그 없음. `` ` ``도 동일.

**근본 원인**: E 항목 수정 과정에서 피부톤 수정자(`U+1F3FB`-`U+1F3FF`)가 `Sk`라서 `_is_emoji_ish()`가 `So` 뿐 아니라 `Sk`(Modifier Symbol) 전체를 emoji-ish로 인정하도록 확장됐다. 그런데 `Sk`에는 ASCII `^`(`U+005E`)와 `` ` ``(`U+0060`)도 포함돼 있고(실제 `unicodedata.category`로 확인), 일반 VS(`U+FE00`-`U+FE0F`)의 "의심 문맥" 판정이 `_is_emoji_ish(prev)`에 의존하므로 이 두 문자 뒤의 VS는 정상 이모지 VS로 오인되어 통과한다. E의 부수 효과다.

**위험도가 Low인 이유**: 캐리어 문자 1개당 살아남는 VS는 1개(두 번째 VS부터는 `prev`가 VS라서 `Sk`도 `So`도 아니므로 제거됨)라, 연속 VS로 대량 데이터를 숨기는 기존 공격은 여전히 차단된다. 다만 `^`/`` ` ``를 여러 번 깔고 각각에 VS 1개씩 붙이는 분산형 스테가노그래피는 이 경로로 통과한다.

**설계 결정**: `_is_emoji_ish()`의 `Sk` 인정 범위에서 **ASCII 범위(`U+0000`-`U+007F`)의 `Sk`를 제외**한다 (`^`, `` ` ``). ASCII `Sk`는 이모지가 될 수 없고, 피부톤 수정자(`U+1F3FB`-`U+1F3FF`)는 계속 인정된다. 비ASCII `Sk`(`´`, `¨`, `¯`, `¸` 등)는 이번 수정 범위에서는 그대로 두며 [열린 질문](#열린-질문)에 남긴다.

**수정 방안**: `_is_emoji_ish()`의 `if cat in ("So", "Sk")` 분기를 `So`는 그대로, `Sk`는 `ord(ch) > 0x7F`일 때만 True가 되도록 좁힌다. 이 함수는 ZWJ 보존(E)에도 쓰이므로 ZWJ 판정에는 영향이 없는지(ASCII `Sk` 양옆의 ZWJ는 원래 emoji 시퀀스가 아님) 함께 확인한다.

**변경 파일**: `src/secnorm/steps/invisible_control_step.py`.

**문서 갱신**: `docs/04-step2-invisible-control-chars.md` 구현 노트에 `_is_emoji_ish()`의 판정 기준(`So`, 비ASCII `Sk`, Regional Indicator, 일부 기호)을 명시.

**테스트**: `^` + `U+FE0F`, `` ` `` + `U+FE0F` → VS 제거 + `high` 플래그 확인. E의 회귀 방지 확인: 피부톤+ZWJ+직업, VS16+ZWJ+성별기호, 가족 이모지 시퀀스가 여전히 보존되는지 재실행. 정상 이모지 + `U+FE0F`/`U+FE0E`가 계속 유지되는지도 확인.

---

## 작업 순서

의존관계상 아래 순서를 권장한다 (각 커밋 단위로 나누고, 항목별로 관련 테스트를 함께 추가):

1. **F** (whitespace CR) — 독립적, 가장 단순.
2. **C** (HTTP 배치 검증) — 독립적.
3. **G** (decode_and_recurse import 버그) — 독립적, A보다 먼저 고쳐야 A의 테스트 결과가 재귀 여부에 흔들리지 않음.
4. **A** (URL always 모드 flag) — G 이후.
5. **D** (HTML entity decoded_markup) — A와 유사한 패턴이라 A 직후 진행하면 문맥 공유.
6. **E** (이모지 ZWJ) — 독립적.
7. **B** (fixpoint/멱등성) — 가장 아키텍처 영향이 크고, A/D/G가 만들어내는 flag들이 fixpoint 재실행에서 이중 계산되지 않는지 함께 검증해야 하므로 마지막에 진행.

> A~G는 `main`에 반영 완료. 아래 후속 항목은 별도 브랜치(`fix/normalization-security-audit-step2-vs`)에서 진행한다.

8. **I** (`Sk` 판정 축소) — 한 줄 수준의 좁은 변경이고 E의 회귀 테스트를 그대로 재사용하므로 먼저 진행.
9. **H** (IVS 허용) — I 이후. 같은 파일·같은 `_classify()` 분기를 건드리므로 I의 판정 기준이 확정된 뒤에 얹는다. H 완료 후 B가 만든 fixpoint 재실행(`security_*` 프리셋)에서 허용된 IVS가 매 반복마다 안정적으로 유지되는지(반복 사이에 제거/재플래그되지 않는지) 확인한다.

각 항목 완료 시 전체 테스트 스위트(`pytest`)와 벤치마크(`pytest-benchmark`, 특히 B 이후 보안 프리셋 3종)를 재실행한다. 문서(`docs/0X-*.md`)는 코드와 같은 커밋에서 함께 갱신한다 (CLAUDE.md 원칙).

## 열린 질문

- **C**: 서버의 캐치올 예외 처리를 400(클라이언트 탓)과 500(서버 내부 오류) 중 어디로 통일할지 — 이번 사례(입력 타입 오류)는 400이 맞지만, 향후 다른 미검증 예외까지 전부 400으로 뭉뚱그리면 진짜 서버 버그도 클라이언트 탓처럼 보일 위험이 있음. 구현 시 판단하거나 별도로 여쭤볼 예정.
- **G**: 재귀 디코딩 시 하위 파이프라인을 항상 `security_balanced`로 고정할지, 호출한 프리셋과 동일한(단, `decode_and_recurse=False`인) 설정을 재사용할지.
- **A**의 `medium` severity 수치는 초안이며, 기존 어드버서리얼 코퍼스 테스트를 실제로 돌려본 뒤 임계값을 재조정할 수 있음.
- **H (분산형 IVS 스테가노그래피)**: 한자마다 IVS 1개씩 붙이는 변형을 어떻게 다룰지. 후보: (a) IVD 등록 조합만 화이트리스트(정확하지만 데이터 테이블이 크고 갱신 필요, `docs/11-dependencies.md`의 "가벼운 의존성" 원칙과 충돌 가능), (b) 텍스트 내 IVS 밀도가 임계치를 넘으면(예: 한자 대비 비율 또는 절대 개수) `medium` 플래그(테이블 없이 구현 가능하지만 임계값 튜닝 필요), (c) 현 정책 유지하고 잔여 위험으로 문서화. 이번 결정(한자 뒤 1개 허용)만으로는 (c) 상태다.
- **H (일반 VS의 한자 뒤 처리)**: `U+FE00`-`U+FE0F`가 CJK 호환 한자(`U+F900`-`U+FAFF`, `U+2F800`-`U+2FA1D`) 뒤에서 쓰이는 표준화 변이 시퀀스(StandardizedVariants)를 허용할지. 현재는 제거 + `high`.
- **I (비ASCII `Sk`)**: `´`, `¨`, `¯`, `¸` 등 비ASCII `Sk` 뒤의 VS도 같은 이유로 통과한다. 피부톤 수정자(`U+1F3FB`-`U+1F3FF`)만 `Sk`로 인정하도록 더 좁힐지(더 엄격하지만 향후 이모지 수정자 추가 시 테이블 갱신 필요) 여부. 더 근본적인 대안은 `emoji-variation-sequences.txt` 기반의 정확한 판정이며, `docs/11-dependencies.md` 원칙상 별도 검토가 필요하다.
