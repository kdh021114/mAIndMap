# 구현 계획: 사용자 피드백 반영

> Flask + Vanilla-JS 그래프-채팅 프로토타입 · 작성일 2026-05-29
> 멀티에이전트 워크플로(코드 매핑 → 항목별 설계 → 종합 + 완전성 비평)로 도출.
> file:line 위치는 코드를 읽은 매핑 에이전트가 산출한 것이며, **착수 직전 재확인** 권장.

## 진행 상황
- ✅ **M0 ① 노드 추가/삭제 버그 + 연타 중복 방지** — 완료·Playwright 검증(add 5연타→1개, del 4연타→1개, 버튼 disabled+스피너).
- ✅ **M1 ② 긴 답변 잘림** — 완료. 토큰 상한 512→2048, `complete()`에 length-truncation 감지(fail-soft)+경고 로그+잘림 안내(채팅 경로만, 한/영), 단위테스트 6종 통과·앱 부팅 확인.
- ✅ **M2 ④ 수식(KaTeX)** — 완료. 코드 인지형 math 추출(마크다운 전 sentinel化→DOM 후 KaTeX 주입)으로 `x_1`/`a*b` 보존, 코드블록/`$5` 안전. 추출기 단위테스트 8종 + 브라우저 검증(인라인/블록 렌더). CDN+SRI.
- ✅ **M2 ③ 최근 채팅 편집/삭제** — 완료. repo(update/delete) + `EditLastUserMessageUseCase`(편집=마지막 교환 삭제 후 재전송→재생성)/`DeleteLastExchangeUseCase` + PATCH/DELETE 라우트 + 인라인 편집 UI. 백엔드 테스트 + 브라우저 검증(편집→재생성, 삭제→빈 상태, non-last 편집 400).
- ✅ **M3 ⑤ 엣지 라벨 토글(기본 OFF) + 점 제거** — 완료. 헤더 토글 버튼 + `edge-labels-hidden` CSS, `edge-label-dot` 완전 제거(양쪽 경로). 브라우저 검증(기본 숨김, 토글 ON/OFF 영속, dot 0개).
- ✅ **M3 ⑥ 미니맵 드래그** — 완료. 헤더 그립으로 패널 이동(bottom/right→left/top, graph-panel 내 클램프, localStorage 영속, resize 재클램프). 토글버튼/본문 pan과 분리. 브라우저 검증(이동·영속·복원).
- ✅ **M4 ⑦ 유스케이스 온보딩 힌트** — 완료(사용자 결정: 모드 전환 기능은 생략, 1회성 정적 힌트만). 첫 방문 시 "여행=Tree, 강의 정리=선형 채팅" 배너 1회 표시 → Dismiss 시 localStorage로 재표시 안 함, 로케일 따라 한/영. 브라우저 검증.

### 전체 피드백 반영 완료 (7/7 항목)
모든 변경은 격리된 임시 데이터/포트에서 Playwright + 백엔드 테스트로 검증. `storage/data.json` 변경은 세션 시작 시점부터 있던 것(내 작업과 무관).

## 확정된 사용자 결정 (2026-05-29)
- **착수**: **M0 버그부터 즉시.** (단, 편집 직전 M0 한정 코드 사실관계는 백그라운드 조사 에이전트로 확정 후 착수 — 아래 참조)
- **② 잘림**: `OPENAI_CHAT_MAX_OUTPUT_TOKENS` **512 → 2048** + incomplete(잘림) 감지/표시 추가.
- **⑤ 엣지 라벨**: 토글 추가하되 **기본 OFF**.
- **③ 채팅 편집**: 최근 user 메시지 편집 시 assistant **재생성**.

---

## Executive Summary

총 7개 작업(P0 버그 1, P1 3, P2 2, P3 1). 강제 의존성은 없으나 **위험도·사용자 가치** 순으로 마일스톤을 구성. 최우선은 노드 추가/삭제가 아예 안 되는 **P0 데드코드 버그**. 이후 P1 3건(긴 답변 잘림, 채팅 편집/삭제, 수식 렌더링), 마지막으로 UX 성격의 P2/P3. 핵심 충돌 지점은 그래프 `app.js`의 `drawNode`/`drawEdge`/`renderAll`을 여러 항목이 동시에 건드린다는 것.

### 권장 실행 순서

| 마일스톤 | 항목 | 이유 |
|---|---|---|
| **M0 (즉시)** | ① 노드 추가/삭제 버그 | 핵심 기능 마비. 최우선. |
| **M1 (LLM 안정화)** | ② 긴 답변 잘림(감지 우선) | 백엔드 격리, 프론트 충돌 없음. |
| **M2 (채팅 기능)** | ③ 채팅 편집/삭제, ④ 수식(KaTeX) | ③은 chat_ui 격리, ④는 양쪽 렌더 경로. |
| **M3 (그래프 UX)** | ⑤ 엣지 라벨 토글(기본 OFF)+점 제거, ⑥ 미니맵 드래그 | 둘 다 그래프 `app.js`/`styles.css`. |
| **M4 (모드)** | ⑦ Tree/Linear 모드 + 온보딩 힌트 | 광범위 레이아웃. 결정 다수 선행. |

---

## ⚠️ 착수 전 선행 조사 (진행 중 — 코드로 규명)

1. **실사용 채팅 경로 확정**: `app/.../app.js` vs `chat_ui/static/app.js` 중복/legacy 여부 → ③④⑦ 위치 결정.
2. **① 백엔드 우선 검증**: 데드코드가 미동작의 *유일* 원인인지, add/delete 엔드포인트 정상인지.
3. **노드 지연 원인**: 타이틀/엣지 LLM 동기 호출? data.json 전체 재기록 I/O?
4. **잘림 원인**: 토큰 상한(512) vs 타임아웃(45s) vs 스트리밍 중단.
5. **엣지 "점" 정체 + 미니맵 구조**: 안전 제거 + 드래그 추가 근거.

---

## ① P0 BUG: 노드 추가/삭제 미동작 + 중복 생성 방지 — M

**진단(가설)**: `drawNode()`(app.js:1293-1294)가 빈 `.node-actions`만 생성. 빌더 `createNodeMicroToolbar()`(1308-1339)·`attachMicroToolbarHover()`(1361-1417)는 **정의만, 호출 0건**. 두 빌더 연결 + 기존 `isSending` 패턴(line 144) 본뜬 **모듈 in-flight 가드(nodeId `Set`)**. `renderAll()`이 `nodeLayer`를 비우므로(876) 가드는 모듈 상태 + `drawNode` 재적용.

**변경 파일**: `app.js`(빌더 연결, 가드, 핸들러들 `createNodeChip`1353/`addChildForNode`3044/`performDeleteNodeById`3139/`deleteSelectedNodes`3154/삭제 다이얼로그 3092 에 가드+try/finally, drawNode 재적용), `styles.css`(disabled/.is-loading).

**리스크**: `runUndoable()`(3048,3142) throw 시에도 가드 해제되게 try/finally가 전체 감싸기. Set 가드(벌크삭제 별도 플래그). 데드코드 의도적 차단 가능성 → 대체 라이브 경로 부재 확인.

**검증**: 호버 시 버튼 등장 → add/delete 동작 → 5연타 시 POST 1건 → 진행 중 비활성+스피너+"생성 지연 가능" 안내 → 오프라인 시 finally 복구.

---

## ② P1: 긴 답변 잘림 — M (감지 우선)

**진단(가설)**: `OPENAI_CHAT_MAX_OUTPUT_TOKENS=512`(config:56) + `_extract_text`(openai_client_factory.py:53-89)가 응답 객체 폐기 → `status:"incomplete"`/`incomplete_details.reason` 감지 못 함. **선행조사 #4로 타임아웃(45s) 여부 먼저 확정.**

**확정 작업**: (1) `OPENAI_CHAT_MAX_OUTPUT_TOKENS` **512 → 2048**(config:56). (2) `complete()`가 incomplete/finish 신호 감지 → 가시적 잘림 마커 + warning 로그(fail-soft). (3) 안정화: 활성 모델이 추론 모델이면 temperature 미지원 → `reasoning_effort`/`text_verbosity` 사용, 비추론 모델 교체 시에만 동작하는 가드된 옵션 temperature 패스스루 추가. ※ 2048은 장문 시 **출력 토큰 비용 최대 ~4배** — 선행조사 #4로 타임아웃(45s)이 진짜 원인이면 토큰만 올려도 증상 잔존하므로 함께 확인.

**변경 파일**: `openai_client_factory.py`(incomplete 감지 + 가드 temperature), 필요 시 `config.py`/`openai_models.py`/`llm_factory.py`/`composition_root.py` 배선.

**검증**: `complete()` 단위 테스트(incomplete→마커+warning, completed→없음). `TEST_MODE=False` 실모델 장문 유도.

---

## ③ P1 FEATURE: 최근 채팅 메시지 편집/삭제 — M (편집 시 재생성)

**접근**: chat_ui 수직 슬라이스. 현재 `chat_ui/repository.py` append-only → update/delete/delete_last_exchange 추가. "최근만" 제약은 유스케이스에서 마지막 user/assistant 쌍 식별. **편집 시 assistant 재생성(확정)**, 삭제는 쌍 함께 제거 기본.

**변경 파일**: `chat_ui/repository.py`, `chat_ui/use_cases.py`(edit_last_user_message→재생성), `chat_ui/routes.py`(PATCH/DELETE), `chat_ui/static/{app.js,index.html,styles.css}`(최근 버블만 UI). ※ 실사용 경로(선행조사 #1) 확정 후 위치 확정.

**리스크**: 첫 메시지 편집 시 **노드 타이틀 + 자식들의 ancestor 컨텍스트 stale**(트리 파급). 재생성 토큰 비용. `streaming.py` 재사용 가능 여부 확인.

**검증**: 최근 user 편집→갱신+재생성, 삭제→쌍 제거, 이전 메시지 UI 미노출, 새로고침 영속.

---

## ④ P1 FEATURE: TeX 수식 렌더링 (KaTeX) — S~M

**접근**: KaTeX(경량·auto-render). **두 렌더 경로** 양쪽 삽입(선행조사 #1로 실사용 경로 확정). `markdown→(sanitize)→renderMathInElement`. 코드블록 `$` 보호.

**변경 파일**: 양쪽 `index.html`(CDN 또는 vendor 번들), 양쪽 `app.js`(DOM 삽입 직후 렌더 + delimiters `$…$ $$…$$ \(…\) \[…\]`).

**검증**: 인라인/블록 렌더, 코드블록 `$` 보존, 마크다운 회귀 없음.

---

## ⑤ P2: 엣지 라벨 ON/OFF 토글(기본 OFF) + 엣지 옆 점 제거 — S~M

**접근**: 같은 `drawEdge` 영역 두 변경. (1) phrase 라벨 전역 토글(헤더 버튼 + localStorage), **기본 OFF 확정**. (2) 엣지 옆 "점"은 선행조사 #5로 정체 확정 후 제거(지오메트리·화살표 유지).

**변경 파일**: `app.js`(drawEdge 라벨 가드 + 점 제거 + 토글 + localStorage), `index.html`(토글 버튼), `styles.css`.

**리스크**: 점이 라벨 앵커/클릭 타겟이면 제거 시 깨짐. ①과 같은 `drawEdge`/`renderAll` → ① 후 진행.

**검증**: 토글 시 전 엣지 라벨 즉시 반영+영속(기본 숨김), 점 제거 후 선/화살표 정상.

---

## ⑥ P2: 미니맵 드래그 — M

**접근**: pointer 드래그(헤더/핸들 또는 모디파이어로 내부 pan/클릭-네비와 구분), 뷰포트 클램프, localStorage 영속. 선행조사 #5로 현재 구조 확정.

**변경 파일**: `app.js`(드래그 핸들러+클램프+영속), `styles.css`(position·커서·핸들), (선택)`index.html`.

**검증**: 끌어 이동+영속, 내부 네비 정상, 화면 밖 불가.

---

## ⑦ P3 DIRECTION: Tree/Linear 모드 + 온보딩 힌트 — M~L

**접근**: 최소 버전 Linear 모드 토글(그래프 숨김+채팅 전체폭) + 여행=Tree/강의=Linear 추천 힌트. 기존 `#mode-indicator` 활용. CSS 클래스 토글 수준, 깊은 리팩터링 회피.

**변경 파일**: `index.html`(토글+힌트), `app.js`(모드 상태+localStorage+클래스 토글), `styles.css`(linear 레이아웃).

**검증**: 토글 시 전환+영속, Tree 회귀 없음.

---

## 남은 결정 (착수 전 확인)

- ③ 삭제 단위 = user+assistant 쌍 vs 개별? / "최근" = 한 메시지 vs 한 교환? / 첫 메시지 편집 시 타이틀·엣지 재생성?
- ④ KaTeX CDN vs vendor(오프라인)?
- ⑤ 점 완전 제거 vs 옵션 숨김?
- ⑥ 드래그 핸들 전체 vs 전용 그립?
- ⑦ 수동 토글만 vs 자동 추천 힌트 포함? / Linear에서 그래프 완전 숨김 vs 축소?

---

## 주의 / 충돌 (Cross-Cutting)

- **C1. 그래프 `app.js`**: ①⑤⑥⑦ 같은 파일 → **①→⑤→⑥→⑦ 순차**. ①의 "재렌더 상태 재적용" 패턴을 ⑤ 라벨 토글이 재사용.
- **C2. 렌더 파이프라인**: ②③④가 메시지 렌더 공통 진입점 → `markdown→sanitize→KaTeX` 단일 함수로 정리, ③ 재렌더도 재사용. ④ 먼저 확정.
- **C3. 이중 채팅 경로**: 선행조사 #1로 확정. ④ KaTeX는 사용 중 모든 경로 적용.
- **C4. localStorage**: ⑤⑥⑦ → `hai:graph:*` 공통 prefix.

---

## 다음 액션
선행조사 5개 결과 보고 → ① 착수(M0) → 마일스톤 순서대로.
