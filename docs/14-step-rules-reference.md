# 14. 단계별 처리 규칙 레퍼런스 (구현 기준)

이 문서는 **현재 코드가 실제로 하는 일**을 단계(step)별로 정리한 참고 자료다. 설계 의도는 `docs/03`~`09`, 이 문서는 "그래서 코드는 어떤 입력을 어떻게 처리하는가"를 다룬다.

- 기준: `main` @ `f6030f2` (2026-09-21). 이후 코드가 바뀌면 이 문서도 함께 갱신한다.
- 예시의 입력/출력은 전부 `src/secnorm/steps/*.py`를 단계별로 단독 실행해 확인한 값이다 (추측 아님). 아래 "확인 방법" 참고.
- **설계 문서와 구현이 다른 부분**은 [알려진 제한과 주의점](#알려진-제한과-주의점)에 모았다.
- 보안 감사 후속 과제 H(일본어 IVS 허용) 및 I(ASCII Sk 제외)는 [`security-audit-fixes-plan.md`](./security-audit-fixes-plan.md)에 따라 구현 완료되어 이 문서에 반영되어 있다.

---

## 1. 한눈에 보기

파이프라인은 항상 아래 순서로 실행된다 (`src/secnorm/presets.py:_build_full_steps`).

| # | 단계 | 이름(`step.name`) | 텍스트를 바꾸나 | flag를 남기나 | 한 줄 요약 |
|---|---|---|---|---|---|
| 1 | Unicode 정규화 | `unicode` | O | X | NFKC(기본)로 호환 문자를 표준형으로 |
| 2 | 비가시/제어 문자 | `invisible_control` | O (제거) | O | 눈에 안 보이는 문자를 제거하고 위험도별로 flag |
| 3 | 공백 정규화 | `whitespace` | O | X | 특수 공백·개행을 통일하고 연속 공백을 접음 |
| 4 | 인코딩/이스케이프 | `encoding_escaping` | O (디코딩) | O | HTML entity, URL `%XX`, `\uXXXX` 디코딩 |
| 5 | 반복 문자 | `repeated_char` | O (접기) | O | 같은 문자의 긴 반복을 상한까지 줄임 |
| 6 | 난독화 | `obfuscation` | O (homoglyph만 기본) | O | 동형 문자 치환, 구분자·leet·base64/hex 탐지 |
| 7 | 언어/구조 메타데이터 | `language_structural` | **X** | X | 텍스트는 그대로 두고 언어·구조 정보만 추출 |

**출력 구조**: 각 단계는 `StepOutput(text, transformations, flags, edits, variants)`를 돌려준다.

- `transformations`: 무엇을 무엇으로 바꿨는지. `rule`이 규칙 이름이다 (예: `strip_zero_width`).
- `flags`: 위험 신호. `category`, `severity`(`low`/`medium`/`high`), `span`(**원문 `raw_text` 좌표**)을 가진다.
- `edits`: span map을 이어 붙이기 위한 변경 구간 (원문 ↔ 정규화 결과 좌표 변환용).
- `variants`: 정규 텍스트와 별개인 "매칭용" 텍스트. 현재는 6단계의 `"aggressive"`만 쓴다.

`security_balanced`/`security_strict`/`llm_input_sanitize`는 여기에 더해 파이프라인 전체를 **텍스트가 안 바뀔 때까지(최대 3회) 다시 실행**한다 ([9. Fixpoint 재실행](#9-fixpoint-재실행-보안-프리셋-3종)).

---

## 2. 프리셋별 설정 차이

| 프리셋 | 실행 단계 | 1단계 form | 3단계 mode | 2단계 VS | 4단계 URL | 4단계 markup flag | 6단계 recurse | 6단계 구분자→정규 텍스트 | fixpoint |
|---|---|---|---|---|---|---|---|---|---|
| `minimal` | 1, 3 | NFC | strict | (2단계 없음) | (4단계 없음) | - | - | - | X |
| `nlp_preprocessing` | 1~5, 7 | NFKC | **structural** | suspicious_only | url_context_only | X | - | - | X |
| `security_balanced` | 1~7 | NFKC | strict | suspicious_only | url_context_only | X | X | X | **O** |
| `security_strict` | 1~7 | NFKC | strict | suspicious_only | **always** | **O** | **O** | **O** | **O** |
| `llm_input_sanitize` | 1~7 | NFKC | strict | **all** | url_context_only | **O** | X | X | **O** |

`security_strict`는 "오탐을 감수하고 최대한 잡는" 프리셋이라 나머지 옵션을 가장 공격적으로 켠다. `llm_input_sanitize`는 프롬프트 인젝션 방어가 목적이라 2단계 VS를 전부 제거하는 것이 핵심 차이다.

---

## 3. 1단계 — Unicode 정규화

`src/secnorm/steps/unicode_step.py`. 텍스트 전체에 `unicodedata.normalize(form, text)` 한 번. **flag는 남기지 않는다.**

| 설정 | 값 | 동작 |
|---|---|---|
| `unicode.form` | `NFKC`(기본), `NFC`, `NFD`, `NFKD` | 정규화 형식. `minimal`만 `NFC` |

변경이 있으면 `rule = "normalize_<form>"`인 `Transformation`이 변경 구간마다 기록된다.

| 입력 | 결과 (NFKC) | 비고 |
|---|---|---|
| `ＡＢＣ１２３＜ｓｃｒｉｐｔ＞` | `ABC123<script>` | 전각 → ASCII. `＜`가 `<`로 바뀌므로 **이후 단계가 진짜 `<script>`로 본다** |
| `ﬁ ① ㎏ ™` | `fi 1 kg TM` | 합자, 원문자, 단위 기호, 상표 기호 |
| `ｶﾀｶﾅ` | `カタカナ` | 반각 가타카나 → 전각 |
| `a b　c d` | `a b c d` | NBSP, 전각 공백, em space가 **이 단계에서 이미 일반 공백**이 됨 |
| 자모 3개(`ᄒ`+`ᅡ`+`ᆫ`) | `한` | 한글 자모 조합 |
| `ＡＢＣ` (NFC) | `ＡＢＣ` | NFC는 호환 문자를 건드리지 않음 |

주의: NFKC는 **되돌릴 수 없다** (`㎏`→`kg`, `™`→`TM`, `①`→`1`). 원문 표기가 중요한 용도에는 `minimal`(NFC)을 쓴다.

---

## 4. 2단계 — 비가시/제어 문자

`src/secnorm/steps/invisible_control_step.py`. 문자를 하나씩 검사해 **유지/제거를 결정**하고, 같은 규칙으로 연속 제거되는 구간은 하나의 `Transformation`/flag로 묶는다.

### 4-1. 규칙 표

`_classify()`는 위에서부터 첫 번째로 맞는 규칙을 적용한다 (순서가 곧 우선순위).

| 순서 | 대상 | 처리 | rule | flag (category / severity) |
|---|---|---|---|---|
| 0 | `preserve_whitelist` (기본 `\t`, `\n`) | 그대로 통과 | - | - |
| 1 | `Cc` 제어 문자 (`\x00`-`\x1F` 중 탭/개행 제외, `\x7F`, `\x80`-`\x9F`) | 제거 (`strip_control=False`면 유지) | `strip_control` | `control_char` / medium |
| 2 | BOM `U+FEFF` | 제거 | `strip_bom` | **맨 앞이면 flag 없음**, 중간이면 `bom_injection` / low |
| 3 | zero-width: `U+200B` ZWSP, `U+200C` ZWNJ, `U+200D` ZWJ, `U+2060` WJ, `U+00AD` SHY | 제거. 단 **ZWJ가 이모지 사이면 유지** ([4-3](#4-3-이모지-zwj)) | `strip_zero_width` | `zero_width_injection` / medium |
| 4 | bidi 제어: `U+202A`-`U+202E`, `U+2066`-`U+2069` | 제거 | `strip_bidi_override` | `bidi_override` / **high** |
| 5 | Tag 문자 `U+E0000`-`U+E007F` | 제거 | `strip_tag_char` | `tag_char_smuggling` / **high** |
| 6 | VS supplement `U+E0100`-`U+E01EF` | CJK 한자 바로 뒤 1개는 유지(일본어 IVS), 그 외는 제거 | `strip_variation_selector` | `tag_char_smuggling` / **high** (유지 시 없음) |
| 7 | VS1-16 `U+FE00`-`U+FE0F` | [4-2](#4-2-variation-selector) 참고 | `strip_variation_selector` | `tag_char_smuggling` / high 또는 없음 |
| 8 | 비정상 공백: `U+180E`, `U+3164`, `U+FFA0` | 제거 | `strip_abnormal_space` | `invisible_spacing` / medium |
| 9 | `Co` Private Use (`U+E000`-`U+F8FF` 등) | `private_use_policy`에 따름 (기본 `flag`) | `strip_private_use` | `private_use_char` / low |
| 10 | `Cn` 미할당 코드포인트 | 제거 (`strip_unassigned=False`면 유지) | `strip_unassigned` | `unassigned_codepoint` / low |

각 규칙은 `strip_*` 설정으로 끌 수 있다 (`strip_bidi_override`, `strip_tag_chars`는 끄는 것을 권장하지 않음).

### 4-2. Variation Selector

일반 VS(`U+FE00`-`U+FE0F`) 및 VS supplement(`U+E0100`-`U+E01EF`) 처리다. `strip_variation_selectors` 설정으로 3가지 모드가 있다.

| 모드 | 동작 |
|---|---|
| `suspicious_only` (기본) | **바로 앞 문자가 emoji-ish이면 일반 VS 유지, CJK 한자 바로 뒤 VS supplement 1개는 유지**, 아니면 제거 + `high` flag |
| `all` | 전부 제거. 이모지 뒤 VS는 **flag 없이** 제거, 의심 문맥이면 `high` flag (`llm_input_sanitize`가 사용, IVS도 제거) |
| `none` | 손대지 않음 |

"emoji-ish"는 `_is_emoji_ish()`가 판정한다: 유니코드 카테고리 `So`, 비ASCII `Sk`(피부톤 수정자 `U+1F3FB`-`U+1F3FF`, ASCII `^`/`` ` ``는 제외), Regional Indicator(`U+1F1E6`-`U+1F1FF`), 일부 기호(♀ ♂ ⚕ ⚖ ✈ ✉ ✊-✍). 실제 이모지 속성 테이블이 아니라 **카테고리 기반 휴리스틱**이다.

| 입력 | 결과 | flag |
|---|---|---|
| `❤` + `U+FE0F` | 유지 | 없음 |
| `❤` + `U+FE0E` (텍스트 표시형) | 유지 | 없음 |
| `❤` + `U+FE0F` + `U+FE0F` | 첫 VS만 유지, 둘째 제거 | `tag_char_smuggling` / high |
| `a` + `U+FE0F` | 제거 | `tag_char_smuggling` / high |
| `^` + `U+FE0F` | 제거 (ASCII `Sk` 제외) | `tag_char_smuggling` / high |
| `葛` + `U+E0100` (일본어 IVS) | 유지 (한자 뒤 1개 허용) | 없음 |
| `葛` + `U+E0100` + `U+E0101` | 둘 다 제거 (연속 2개 이상) | `tag_char_smuggling` / high |
| `❤` + `U+FE0F` (`all` 모드) | 제거 | 없음 |
| `a` + `U+FE0F` (`none` 모드) | 유지 | 없음 |

VS supplement(`U+E0100`-`U+E01EF`)는 원칙적으로 제거되지만, **CJK 한자 바로 뒤에 정확히 1개** 오는 경우 일본어 IVS(이체자 선택자)로 인정되어 보존된다(플래그 없음). 2개 이상 연속되거나 비한자 뒤에 오면 스테가노그래피로 간주되어 `high` 플래그와 함께 제거된다.

### 4-3. 이모지 ZWJ

ZWJ(`U+200D`)는 **양옆의 "실제 문자"가 모두 emoji-ish일 때만** 유지한다. "실제 문자"를 찾을 때 사이에 낀 VS(`U+FE00`-`U+FE0F`, `U+E0100`-`U+E01EF`)는 건너뛴다 (`_skip_vs_backward/forward`). 그래서 `✍`+VS16+ZWJ+`♀`+VS16 같은 시퀀스도 보존된다.

| 입력 | 결과 | flag |
|---|---|---|
| `👨` ZWJ `👩` | 유지 | 없음 |
| `a` ZWJ `b` | ZWJ 제거 | `zero_width_injection` / medium |

### 4-4. 그 밖의 실측 예시

| 입력 | 결과 | flag |
|---|---|---|
| `무료` ZWSP `배포` | `무료배포` | `zero_width_injection` / medium |
| `pass` SHY `word` | `password` | `zero_width_injection` / medium |
| `a\x00b\x7fc` | `abc` | `control_char` / medium ×2 |
| `a\tb\nc` | 그대로 | 없음 (탭·개행은 화이트리스트) |
| BOM + `hello` | `hello` | **없음** (맨 앞 BOM은 인코딩 부산물로 간주) |
| `he` BOM `llo` | `hello` | `bom_injection` / low |
| RLO `reversed` PDF | `reversed` | `bidi_override` / high ×2 |
| `admin` + Tag 문자 2개 | `admin` | `tag_char_smuggling` / high (연속 구간 1건) |
| `a` `U+3164` `b` `U+FFA0` `c` `U+180E` `d` | `abcd` | `invisible_spacing` / medium ×3 |
| `a` `U+E000` `b` | 유지 | `private_use_char` / low (기본 `flag`) |
| `a` `U+0378` `b` | `ab` | `unassigned_codepoint` / low |

`private_use_policy`: `keep`(유지, flag 없음) / `flag`(유지 + low flag, 기본) / `strip`(제거 + low flag).

**출력에서 flag가 없는 제거**: 맨 앞 BOM, `all` 모드의 이모지 뒤 VS. 이 두 경우는 `severity=None`이라 `Transformation`만 남는다.

---

## 5. 3단계 — 공백 정규화

`src/secnorm/steps/whitespace_step.py`. **flag를 남기지 않는다.** rule은 항상 `normalize_whitespace`.

처리 순서:

1. 개행 통일: `\r\n` → `\n`, 남은 단독 `\r` → `\n`.
2. 변환 테이블(`str.translate`)로 특수 공백 치환.
3. 연속 공백 접기 (`mode`에 따라 다름).
4. `trim_edges`면 양끝의 ` `, `\t`, `\n`, `\r` 제거.

| 대상 | 치환 | 조건 |
|---|---|---|
| `U+00A0`, `U+2007`, `U+202F`, `U+2000`-`U+200A` | 일반 공백 | 항상 |
| `U+2028`, `U+2029`, `U+000B`(VT), `U+000C`(FF) | `\n` | 항상 |
| `U+3000` (전각 공백) | 일반 공백 | `preserve_ideographic_space=False`(기본) |
| `\t` | 일반 공백 | `tab_policy="to_space"`(기본). `"keep"`이면 접기 규칙도 탭을 건드리지 않음 |

| 모드 | 연속 공백 접기 규칙 | 용도 |
|---|---|---|
| `strict` (기본) | `[ \n]+` → 공백 1개. **개행도 공백이 됨** | 매칭·필터링 |
| `structural` | 공백 2개 이상 → 1개, 개행 3개 이상 → 2개. 개행 1~2개는 보존 (단락 구분 유지) | NLP 전처리 |

| 입력 | 결과 | 모드 |
|---|---|---|
| `a   b\n\n\nc` | `a b c` | strict |
| `a   b\n\n\n\nc\n\nd` | `a b\n\nc\n\nd` | structural |
| `l1\r\nl2\r\n\r\nl3` | `l1\nl2\n\nl3` | structural |
| `a　b` | `a b` | 기본 |
| `a　b` | `a　b` | `preserve_ideographic_space=True` |
| `  \t hi \n ` | `hi` | 기본 |
| `  hi  ` | ` hi ` | `trim_edges=False` |
| `a` ZWSP `b` | 그대로 | ZWSP는 **2단계** 담당이라 여기선 안 건드림 |

> **주의**: 1단계(NFKC)가 이미 NBSP·`U+3000`·`U+2000`대 공백을 일반 공백으로 바꾸고, 2단계가 `\r`·VT·FF를 제거하므로, 이 단계의 해당 규칙이 **실제로 일하는 프리셋은 `minimal`뿐**이다. [알려진 제한 1](#알려진-제한과-주의점) 참고.

---

## 6. 4단계 — 인코딩/이스케이프

`src/secnorm/steps/encoding_escaping_step.py`. 아래 하위 변환을 **이 순서로** 연쇄 실행한다 (앞 결과가 뒤 입력).

### 6-1. HTML entity (`decode_html_entities`, 기본 켜짐)

`html.unescape()`로 이름(`&lt;`)·10진(`&#65;`)·16진(`&#x41;`) entity를 모두 디코딩. rule: `decode_html_entity`.

| 입력 | 결과 |
|---|---|
| `&lt;b&gt; &amp; &#65; &#x41; &nbsp;x` | `<b> & A A \xa0x` |

`flag_decoded_markup=True`(`security_strict`, `llm_input_sanitize`)일 때만: **이번 디코딩이 새로 만든** 구간이 태그 시작(`<[a-zA-Z/!]`)처럼 보이면 `decoded_markup` / medium flag.

| 입력 | `flag_decoded_markup` | flag |
|---|---|---|
| `&lt;script&gt;alert(1)&lt;/script&gt;` | False | 없음 |
| 위와 같음 | True | `decoded_markup` / medium ×2 |
| `<script>x</script>` (원래부터 리터럴) | True | 없음 — 디코딩이 만든 게 아니므로 |
| `1 &lt; 2` | True | 없음 — `<` 뒤가 공백이라 태그 시작이 아님 |

### 6-2. URL percent-encoding (`decode_url_encoding`)

| 모드 | 디코딩 대상 | flag |
|---|---|---|
| `url_context_only` (기본) | `https?://...` **안의** `%XX`만 | URL 밖의 `%XX`는 **디코딩하지 않고** `encoded_payload` / low (`percent_encoding_outside_url`) |
| `always` (`security_strict`) | 텍스트 전체 `%XX` | 모든 `%XX`마다 `encoded_payload` / **medium** (`percent_encoding_decoded_always_mode`) |
| `off` | 없음 | 없음 |

| 입력 | 모드 | 결과 | flag |
|---|---|---|---|
| `http://a.com/%3Cb%3E` | url_context_only | `http://a.com/<b>` | 없음 |
| `hello%20world %3Cscript%3E` | url_context_only | 그대로 | low ×3 |
| `..%2f..%2fetc%2fpasswd` | always | `../../etc/passwd` | medium ×3 |
| `a%20b` | off | 그대로 | 없음 |

### 6-3. 유니코드 이스케이프 (`unicode_escape_policy`)

인식 패턴: `\uXXXX`, `\UXXXXXXXX`, `\xXX`, `\N{NAME}`.

| 정책 | 동작 |
|---|---|
| `decode_and_flag` (기본) | 디코딩 + 패턴마다 `encoded_payload` / medium (`unicode_escape_sequence`). rule: `decode_unicode_escape` |
| `flag_only` | 디코딩 없이 flag만 |
| `ignore` | 아무것도 안 함 |

| 입력 | 결과 |
|---|---|
| `A \x42 ​` | `A B` + ZWSP 문자 (flag medium ×3) |
| `\uZZZZ \U00110000 \N{NOPE}` | **그대로 유지** (잘못된 이스케이프는 디코딩 실패 시 원문 유지). flag는 형식이 맞는 것만 (이 입력은 2건) |

디코딩으로 **ZWSP 같은 비가시 문자가 새로 생길 수 있다.** 이 단계 뒤에는 2단계가 다시 돌지 않으므로, 그 처리는 [fixpoint 재실행](#9-fixpoint-재실행-보안-프리셋-3종)이 맡는다.

### 6-4. Mojibake 복구 (`mojibake_repair`, **기본 꺼짐**, 모든 프리셋에서 꺼짐)

선택 의존성 `ftfy`가 있을 때만 동작 (없으면 조용히 건너뜀). `Ã©tÃ©` → `été`. `metadata["ftfy_operations"]`에 복구 작업 목록이 남는다. flag는 없다.

---

## 7. 5단계 — 반복 문자

`src/secnorm/steps/repeated_char_step.py`. 텍스트를 **자소 클러스터(`\X`)** 단위로 나누고, **연속으로 같은 클러스터**가 상한(cap)을 넘으면 cap개로 접는다. rule: `collapse_run`.

### 7-1. 카테고리별 상한

`_get_cap()`이 위에서부터 판정한다.

| 순서 | 카테고리 | 판정 | 기본 cap | 설정 |
|---|---|---|---|---|
| 1 | 공백 | `Z*`, 공백/탭/개행 | **제한 없음** (접지 않음) | - |
| 2 | 이모지 | `emoji` 라이브러리(없으면 `So`) | 3 | `emoji_cap` |
| 3 | 한글 자모 | `U+3131-318E`, `U+1100-11FF`, `U+A960-A97C`, `U+D7B0-D7FB` | 3 | `jamo_cap` |
| 4 | 구두점·기호 | `P*`, `Sm`, `Sc`, `Sk`, `So` | 3 | `punctuation_cap` |
| 5 | 그 외 전부 (문자, **숫자** 포함) | - | **2** | `default_cap` |

`category_overrides`(`{"emoji": 5, "default": 4, ...}`)로 카테고리별 cap을 덮어쓸 수 있다.

**flag**: 접힌 반복 길이가 `min_run_length_to_flag`(기본 5) **이상**이면 `excessive_repetition` / low. 4번 반복은 접지만 flag는 없다.

| 입력 | 결과 | flag |
|---|---|---|
| `coooool sooooo goooood` | `cool soo good` | `repeated_o` ×3 |
| `ㅋㅋㅋㅋㅋㅋ ㅠㅠㅠㅠ` | `ㅋㅋㅋ ㅠㅠㅠ` | `repeated_ㅋ` ×1 (6회만 flag, 4회는 접기만) |
| `하하하하하하 ㅎㅎㅎㅎ` | `하하 ㅎㅎㅎ` | `repeated_하` (완성형 음절은 jamo가 아니라 cap 2) |
| `wow!!!!!!! ...... ?????` | `wow!!! ... ???` | 7·6·5회라 각각 flag |
| `😂😂😂😂😂😂` | `😂😂😂` | flag |
| `a` + 공백 10개 + `b` | 그대로 | 공백은 5단계가 안 건드림 (3단계 담당) |
| `aaaa bbbbb` | `aa bb` | `bbbbb`만 flag (5회) |
| `aaaaa` (`default` override 4) | `aaaa` | flag |

참고: 같은 한글 자모만으로 이루어진 여러 글자짜리 자소 클러스터는 낱개로 풀어서 센다 (코드 `apply()`의 "Unpack clusters" 블록). 그래서 자모가 한 클러스터로 묶여 들어와도 반복으로 인식된다.

---

## 8. 6단계 — 난독화

`src/secnorm/steps/obfuscation_step.py`. 원칙: **"정규 텍스트는 보수적으로, 매칭용 변형(variant)은 공격적으로"**. 오탐 위험이 큰 변환은 `normalized_variants["aggressive"]`에만 반영한다. `obfuscation.enabled=False`면 통째로 건너뛴다.

하위 단계는 6-1 → 6-2 → 6-3 → 6-4 순이고, **정규 텍스트(`canonical`)에 반영되는 것은 6-1과 (조건부) 6-2뿐**이다.

| 하위 | 규칙 | 정규 텍스트에 반영 | aggressive variant | flag |
|---|---|---|---|---|
| 6-1 | Homoglyph | **O** | O | `homoglyph` / **high** (문자마다) |
| 6-2 | 구분자 삽입 | 조건부 | O | `separator_injection` / low |
| 6-3 | Leetspeak | X | O | `leetspeak` / low (3회 이상) |
| 6-4 | base64 / hex | X | (leet 변환이 일부 걸릴 수 있음) | `encoded_payload` / medium |

### 8-1. Homoglyph (`homoglyph_normalize`, 기본 켜짐)

`CONFUSABLE_MAP`(UTS #39 기반, 현재 **64개**, 버전 16.0.0; 키는 키릴 31·그리스 23·기타)에 있는 문자를 라틴 문자로 1:1 치환한다. 모든 치환은 한 글자 → 한 글자다. 치환마다 `homoglyph` / high flag.

**단일 외국어 텍스트는 건드리지 않는다.** 라틴 문자가 5% 이하이고 키릴·그리스 문자가 알파벳의 80% 초과면 그냥 러시아어/그리스어 문장으로 보고 치환을 건너뛴다.

| 입력 | 결과 | 비고 |
|---|---|---|
| `pаypal аdmin` (`а`=키릴) | `paypal admin` | flag ×2 (`homoglyph_а_to_a`) |
| `hello ρaypal` (`ρ`=그리스) | `hello paypal` | flag ×1 |
| `привет мир` | 그대로 | 순수 키릴 문장이라 건너뜀 |

### 8-2. 구분자 삽입 (`separator_injection_detect`, 기본 켜짐)

패턴: **글자/숫자 1개 + 구분자(공백 `.` `_` `-` `~` `*`)** 가 **4글자 이상** 이어진 것 (`f.r.e.e`, `f r e e`). 3글자(`a.b.c`)는 안 걸린다. 걸리면 low flag.

- `aggressive` variant에는 구분자를 **제거한** 형태가 들어간다.
- **정규 텍스트에도 반영하는 경우**: (a) `separator_injection_collapse_in_canonical=True` (`security_strict`) 또는 (b) `dictionary`가 주어졌고 접은 토큰이 사전에 있을 때. rule: `collapse_separator`.

| 입력 | 설정 | 정규 텍스트 | aggressive |
|---|---|---|---|
| `f.r.e.e m o n e y` | 기본 | 그대로 | `freemoney` (`m o n e y`가 `f.r.e.e`와 합쳐져 한 덩어리가 됨) |
| `f.r.e.e money` | `collapse_in_canonical=True` | `free money` | - |
| `f.r.e.e money` | `dictionary={"free"}` | `free money` | - |
| `a.b.c` | 기본 | 그대로 | flag 없음 |

### 8-3. Leetspeak (`leetspeak_detect`, 기본 켜짐)

매핑: `0→o 1→i 3→e 4→a 5→s 7→t @→a $→s`. **공백으로 나눈 토큰 안에 글자와 leet 문자가 모두 있을 때만** 치환한다 (숫자만 있는 토큰 `911`은 안 건드림). **정규 텍스트는 절대 바꾸지 않고 aggressive variant에만** 반영한다.

flag는 치환 횟수가 **3 이상**일 때만 `leetspeak` / low (span은 텍스트 전체).

| 입력 | aggressive | flag |
|---|---|---|
| `fr33 m0n3y h4ck` | `free money hack` | O (치환 5회) |
| `h4ck` | `hack` | 없음 (1회) |

### 8-4. 인코딩된 페이로드 (`encoded_payload_detect`, 기본 켜짐)

| 패턴 | flag |
|---|---|
| base64: 공백 경계, 16자 이상, 4자 블록 + 패딩 | `encoded_payload` / medium (`base64_payload`) |
| hex: 공백 경계, 16자 이상 | `encoded_payload` / medium (`hex_payload`) |

텍스트는 바꾸지 않고 **탐지만** 한다. 예: `aGVsbG8gd29ybGQgaGVsbG8gd29ybGQ=` → base64 flag.

**`decode_and_recurse=True`(`security_strict`)**: base64가 유효한 UTF-8로 디코딩되고 크기 비율(`max_decoded_size_ratio`, 기본 10배)을 넘지 않으면, 디코딩 결과를 하위 파이프라인에 넣어 **거기서 나온 flag를 부모 flag로 옮긴다** (`detail="decoded_payload:<원래 detail>"`, span은 원본 base64 구간). 재귀 깊이는 `max_recursion_depth`(기본 1). 디코딩 실패(`binascii.Error`, `UnicodeDecodeError`, `ValueError`)는 조용히 무시한다.
디코딩된 텍스트 자체는 결과에 남지 않고 **flag만** 전달된다.

---

## 9. Fixpoint 재실행 (보안 프리셋 3종)

`src/secnorm/pipeline.py:run()`. `stabilize_output=True`(`security_*`, `llm_input_sanitize`)면 한 번 실행한 결과를 **다시 파이프라인에 넣어**, 결과가 입력과 같아지거나 `max_stabilize_iterations`(기본 3)에 이를 때까지 반복한다. 1회차 결과를 무조건 한 번 더 돌려 확인하므로 **보안 프리셋은 최소 2회 실행**된다. 정상 입력은 2회차 결과가 같아 거기서 끝난다 (그 2회차의 flag·transformation은 기록하지 않는다).

- 재실행에서 나온 flag·transformation은 `metadata["stabilize_iteration"]`에 반복 번호(2 이상)가 붙는다.
- flag의 span은 누적 span map으로 **원문 좌표**로 되돌려 저장한다.

실측 (`hello` + 리터럴 `​`(6글자) + `world`):

| 프리셋 | 결과 | flag |
|---|---|---|
| `minimal` | `hello​world` (리터럴 그대로) | 없음 (4단계 없음) |
| `nlp_preprocessing` | `hello`+**실제 ZWSP**+`world` | `encoded_payload` / medium만 |
| `security_balanced` / `security_strict` / `llm_input_sanitize` | `helloworld` | `encoded_payload` + **`zero_width_injection` (iteration 2)** |

`nlp_preprocessing`은 fixpoint가 없어서 4단계가 디코딩해 만든 ZWSP가 **남는다.** 이중 URL 인코딩도 비슷하다: `%253Cscript%253E`는 `security_strict`(`always`)에서 2회 반복 끝에 `<script>`가 되고, `security_balanced`(`url_context_only`)에서는 URL 밖이라 디코딩되지 않고 low 수준 flag만 남는다.

---

## 10. 7단계 — 언어/구조 메타데이터

`src/secnorm/steps/language_structural_step.py`. **텍스트를 절대 바꾸지 않는다.** 결과는 `NormalizationResult.language`에 담긴다.

### 10-1. 언어 판정 (`_detect_language_raw`)

스크립트별 문자 수(`Hangul`, `Hiragana`, `Katakana`, `Han`, `Latin`, `Cyrillic`, `Greek`, `Arabic`, `Hebrew`)를 세어 **아래 순서대로** 판정한다. 첫 번째로 맞는 규칙이 결과가 된다. 판정 가능한 글자 수가 `min_text_length_for_detection`(기본 2) 미만이면 `None`.

| 순서 | 조건 | 결과 (confidence) |
|---|---|---|
| 1 | 히라가나/가타카나가 하나라도 있음 | `ja` (0.95) |
| 2 | 한글 ≥ 판정 대상 글자의 30% | `ko` (0.95) |
| 3 | 키릴/그리스/아랍/히브리 ≥ 50% | `ru` / `el` / `ar` / `he` (0.90) |
| 4 | 한자만 있음 (한글·가나 없음) | 4a → 4b → `None` |
| 5 | 라틴 ≥ 50% | 5a → 5b → `en` (0.90) |

- **4a (한자 전용 마커)**: 일본 전용 한자만 있으면 `ja`, 중국어(간체/번체) 전용 한자만 있으면 `zh` (0.95). 둘 다 있거나 둘 다 없으면 4b.
- **4b (`langdetect` 폴백)**: `fallback_detector="langdetect"`일 때만. 시드 고정(`seed=0`)으로 결정적. `zh*`→`zh`, `ja`/`ko`/`en` 인정. 그 외는 `None`.
- **5a (라틴 방언 마커)**: `detect_latin_dialects=True`일 때. `ñ ¿ ¡`→`es`, `ß`→`de`, `œ`→`fr`, `ç`(스페인어 마커 없을 때)→`fr`, `ä ö ü`(스페인어 마커 없을 때)→`de`.
- **5b**: `langdetect`에서 `es/fr/de/it/pt/en`이며 확률 ≥ 0.7이면 채택.
- `supported_languages`가 지정되면 그 밖의 결과는 `None`으로 바꾼다 (기본 `None` = 제한 없음).

| 입력 | 결과 |
|---|---|
| `안녕하세요` | `ko` 0.95 |
| `こんにちは漢字` | `ja` 0.95 (혼합 스크립트로도 표시) |
| `你好世界` | `zh` (langdetect 확률) |
| `Hola, ¿cómo estás?` | `es` 0.95 |
| `Привет мир` | `ru` 0.90 |
| `안녕 hello` | `en` 0.90, `is_mixed_script=True` |

### 10-2. 그 밖의 메타데이터

- `script_ratios`: 스크립트별 문자 비율 (`Common`=공백·구두점·숫자·기호, `Other`=그 외).
- `is_mixed_script`: `Common`/`Other`를 뺀 **상위 두 스크립트가 모두 `mixed_script_threshold`(기본 0.15) 이상**.
- `structural`: `has_html`(`<태그>`), `has_markdown`, `has_url`, `has_email`, `has_code_block`(펜스 또는 4칸/탭 들여쓰기), `sentence_count`(`. ! ? 。 ！ ？ \n` 기준), `word_count`(단어 + CJK 글자 수), `direction`(`rtl`은 아랍/히브리 문자 수 ≥ LTR 문자 수일 때).

---

## 알려진 제한과 주의점

아래는 코드를 읽고 실제로 돌려서 확인한 **현재 동작의 함정**이다. 아직 이슈로 등록되거나 수정 계획이 잡힌 것은 아니다.

1. **2단계가 `\r`·VT·FF를 지워서 3단계 규칙이 도달하지 못한다.**
   `\r`(CR), `\x0b`(VT), `\x0c`(FF)는 `Cc`라서 2단계에서 **삭제**된다. 그래서 2단계가 켜진 프리셋에서는 단독 CR/VT/FF가 줄바꿈이 아니라 아무것도 아니게 되어 **앞뒤 단어가 붙는다.**
   | 입력 | `minimal` | `nlp_preprocessing` / `security_balanced` |
   |---|---|---|
   | `a\rb` | `a b` | `ab` |
   | `a\x0bb` | `a b` | `ab` |
   | `x\r\ny` | `x y` | `x\ny` (nlp) / `x y` (balanced) |

   CRLF는 `\r`만 지워지고 `\n`이 남아 결과가 같아지지만, 구형 Mac 스타일 단독 CR이나 VT/FF로 구분된 텍스트는 단어가 합쳐진다. 3단계 문서의 "CR/VT/FF는 줄바꿈으로 정규화" 조항은 `minimal`에서만 실제로 적용된다.

2. **5단계가 숫자와 일반 문자를 cap 2로 접는다.**
   `1000000 won, 3.14159, 555-1111` → `100 won, 3.14159, 55-11`, `www.example.com` → `ww.example.com`. 연속으로 같은 숫자가 3개 이상 나오는 값(금액, 전화번호, 계좌번호)이 **의미가 바뀐다.** 그대로 두려면 `category_overrides={"default": <큰 값>}`이 필요하다.

3. **2단계가 ZWNJ(`U+200C`)를 언어와 무관하게 제거한다.**
   `می` ZWNJ `خواهم`(페르시아어) → `میخواهم`. `docs/04`는 "ZWNJ/ZWJ가 서체 결합에 쓰이는 언어 문맥 예외 여지"를 언급하지만 **구현되어 있지 않다.** (이모지 ZWJ만 예외.)

4. **일본어 IVS 및 `^`·`` ` `` 뒤 VS 처리 (해결 완료).** 2단계 VS 정책의 두 결함(H, I)은 `fix/normalization-security-audit-step2-vs` 브랜치에서 해결되었다 (CJK 한자 바로 뒤 VS supplement 1개 허용 및 ASCII `Sk` emoji-ish 제외). 단, 한자마다 IVS를 1개씩 분산 배치하는 분산형 IVS 스테가노그래피는 IVD 데이터베이스 미검증으로 인한 알려진 잔여 위험으로 남는다.

5. **6단계 aggressive variant는 base64/hex 토큰도 leet 치환한다.**
   `aGVsbG8gPHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==`의 variant는 `aGVsbG8gPHNjcmlwdDshbGVydCgx...`로 **원본이 깨진다.** 또 16자 이상 hex 문자열(`48656c6c6f...`)이 숫자·문자 혼합이라 `leetspeak` flag도 함께 발생한다. 정규 텍스트는 영향이 없고, variant로 매칭할 때만 문제가 된다.

6. **`decode_and_recurse`의 하위 파이프라인은 항상 기본 설정이다.**
   하위 실행이 `build_preset("security_balanced")`의 단계 목록에 **기본 `NormalizationConfig()`** 를 씌운 것이라(fixpoint 꺼짐, 기본 옵션), 호출한 프리셋(`security_strict`)의 옵션이 재귀에는 적용되지 않는다. 디코딩된 텍스트 자체는 결과에 남지 않고 flag만 부모 span으로 올라온다. 또 라이브러리는 **콘텐츠 패턴 탐지(`<script>` 등)를 하지 않으므로** `<script>`를 담은 base64도 디코딩 결과에서 추가 flag가 나오지 않는다 (`docs/06`의 "디코딩"과 "페이로드 내용 탐지"를 분리하는 설계). 이 정책은 `security-audit-fixes-plan.md` G의 열린 질문과 같은 주제다.

7. **7단계가 `docs/01`의 "v1 = ko/en/ja/zh"보다 넓게 판정한다.**
   Phase 11 확장으로 `ru/el/ar/he/es/de/fr/it/pt`도 반환한다. 4개 언어로 제한하려면 `supported_languages=("ko","en","ja","zh")`를 지정한다 (기본은 제한 없음).

8. **`nlp_preprocessing`에는 fixpoint가 없다.** 4단계가 디코딩으로 만든 비가시 문자나 이중 인코딩은 **한 번 더 정규화해야** 사라진다 ([9장](#9-fixpoint-재실행-보안-프리셋-3종)).

---

## 확인 방법

이 문서의 예시는 다음 방식으로 확인했다. 재현하려면 저장소 루트에서:

```python
from secnorm import NormalizationPipeline, NormalizationConfig
from secnorm.steps import InvisibleControlStep

cfg = NormalizationConfig(enabled_steps={"invisible_control"})
result = NormalizationPipeline([InvisibleControlStep()], cfg).run("무료​배포")
print(result.normalized_text, [(f.category, f.severity) for f in result.flags])
```

단계를 하나만 넣은 파이프라인으로 실행하면 그 단계의 규칙만 관찰할 수 있다. 프리셋 전체 동작은 `secnorm.normalize(text, preset="security_balanced")`로 확인한다.
