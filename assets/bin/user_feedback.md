# 📋 사용자 피드백 정리 (User Feedback → Action Items)

사용자 테스트 및 사용 과정에서 수집한, **프로젝트에 반영했으면 하는 피드백 모음**입니다.
카테고리·우선순위별로 분류했고, 코드베이스 기준 예상 작업 위치를 함께 표기했습니다.

> 작성일: 2026-05-29
> (교수/동료의 제안서 리뷰는 별도 파일 [`feedback.md`](feedback.md) 참고)

---

## 🎯 핵심 인사이트 (User Testing Findings)

사용 맥락(use case)에 따라 Tree UI의 효용이 크게 갈린다는 점이 가장 중요한 발견입니다.

| 사용 맥락 | Tree UI 만족도 | 시사점 |
|---|---|---|
| **여행 등 다방면(multi-faceted) 주제** | ⬆️ 확 올라감 | 분기가 많고 비교·탐색이 필요한 주제에 Tree UI가 강점. **핵심 타겟 시나리오로 강조.** |
| **강의안/강의 내용 정리** | ⬇️ 이점 상대적으로 적음 | 선형적 흐름이라 Tree 구조의 인지 부담이 큼. **Linear Chat UI가 더 선호될 가능성.** |

**→ 액션 아이템**
- [ ] Tree UI는 "여러 갈래로 탐색하는 주제"(여행 계획, 제품 비교, 의사결정 등)를 **대표 유스케이스로 포지셔닝**
- [ ] 강의 정리 등 **선형 작업에는 Linear Chat UI를 기본/추천**으로 안내하거나, UI 모드 추천 로직 검토
- [ ] 두 UI 간 전환을 사용자가 쉽게 선택할 수 있도록 진입점 강화 (`chat_ui/`, `app/presentation/web/static/app.js`)

---

## 🐛 버그 수정 (Bug Fixes) — 최우선

| 항목 | 문제 | 예상 위치 |
|---|---|---|
| 노드 추가/삭제 불가 | 노드 추가·삭제가 동작하지 않는 버그 | `app/application/graph_use_cases.py`, `app/presentation/web/routes.py`, `app/presentation/web/static/app.js` |

- [ ] **노드 추가/삭제 안 되는 버그 수정** (기능 자체가 막혀 있어 최우선)

---

## ⚡ 성능 & 모델 튜닝 (Performance & Model Tuning)

| 항목 | 문제 | 제안 |
|---|---|---|
| 노드 추가/삭제 딜레이 | 생성에 지연이 있어, 사용자가 버튼을 여러 번 눌러 **노드가 중복 생성**됨 | (1) 버튼 연타 방지(로딩 중 비활성화/디바운스) (2) 생성 중 로딩 인디케이터 표시 (3) **딜레이가 있을 수 있음을 사전 안내** |
| 답변 중간 잘림 | 답변이 길어지면 중간에 끊김 | (1) **`OPENAI_CHAT_MAX_OUTPUT_TOKENS` 상향** (현재 `512`) (2) 사용 중 출력 안정화를 위한 파라미터 조정 |

- [ ] 노드 생성 버튼 **연타 방지 + 로딩 상태 표시** (중복 생성 방지) — `app/presentation/web/static/app.js`
- [ ] 노드 생성 시 **"딜레이가 생길 수 있다"는 안내 UI** 추가
- [ ] `OPENAI_CHAT_MAX_OUTPUT_TOKENS` 상향 (현재 `512`, 위치: `config.py:67`)
- [ ] 출력 안정화 검토 — 현재 모델은 `temperature` 대신 `OPENAI_REASONING_EFFORT`/`OPENAI_TEXT_VERBOSITY` 사용 (`config.py:65-66`). temperature 지원 모델로 바꾸면 **temperature 하향**으로 답변 잘림/불안정 완화 가능

---

## ✨ 기능 추가 (New Features)

| 항목 | 내용 | 예상 위치 |
|---|---|---|
| 최근 채팅 수정/삭제 | **가장 최근 채팅을 수정·삭제**하는 기능 | `chat_ui/use_cases.py`, `chat_ui/routes.py`, `app/application/chat_use_cases.py` |
| TeX 수식 지원 | 수식을 **TeX로 렌더링**(KaTeX/MathJax 등) | `app/presentation/web/static/app.js`, `app/presentation/web/static/index.html` |
| 엣지 이름 ON/OFF | **엣지 이름 표시 토글** 추가 | `app/presentation/web/static/app.js`, `app/presentation/web/static/styles.css` |

- [ ] 가장 최근 채팅 **수정 및 삭제** 기능
- [ ] **TeX 수식 렌더링** 지원 (KaTeX/MathJax 라이브러리 추가)
- [ ] **엣지 이름 ON/OFF 토글**
  - ⚠️ 참고: 엣지 이름 붙이기가 **강의 내용 정리 task에서는 생각보다 효과적이지 않았음.** → 기본값 OFF 검토 또는 다방면 주제에서만 강조

---

## 🎨 UI / 시각 개선 (UI & Visual)

| 항목 | 내용 | 예상 위치 |
|---|---|---|
| 엣지 옆 동그라미 | 엣지 옆에 표시되는 **동그라미 삭제 검토** | `app/presentation/web/static/app.js`, `app/presentation/web/static/styles.css` |
| 미니맵 이동 | **미니맵 윈도우를 옮길 수 있도록** 수정 (드래그 이동) | `app/presentation/web/static/app.js`, `app/presentation/web/static/styles.css` |

- [ ] 엣지 옆 동그라미 삭제(또는 표시 옵션화) 검토
- [ ] 미니맵 윈도우를 **드래그로 이동 가능**하게 수정

---

## 📌 우선순위 요약

1. **🐛 버그** — 노드 추가/삭제 불가 (기능 차단, 즉시 수정)
2. **⚡ 성능/안정성** — 노드 생성 딜레이·중복, 답변 잘림 (체감 품질 직결)
3. **✨ 기능** — 최근 채팅 수정/삭제, TeX 수식, 엣지 이름 토글
4. **🎨 UI** — 엣지 동그라미, 미니맵 이동
5. **🎯 방향성** — 유스케이스별 UI 모드 포지셔닝(여행=Tree, 강의=Linear)

> 예상 위치는 현재 디렉터리 구조(`app/`, `chat_ui/`, `config.py`) 기준 추정이며, 실제 작업 시 확인 필요.
