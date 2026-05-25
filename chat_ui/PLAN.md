# chat_ui 구현 계획

ChatGPT 비슷한 선형 채팅 UI. 기존 `app/` 인프라 최대 재사용.

---

## 0. 한 줄 요약

`/chat` 경로에 별도 Flask blueprint. 좌측 대화 목록, 가운데 메시지, 마크다운 렌더, 스트리밍 응답, 한/영 토글. 그래프 코드(`app/`)는 건드리지 않음.

---

## 1. 재사용 vs 신규

| 영역 | 재사용 | 신규 |
|---|---|---|
| Flask 앱 | `composition_root.create_app` 그대로 | blueprint 등록 한 줄 추가 |
| LLM 호출 | `app/infrastructure/llm/` (`LlmProviderFactory.chat_model`) | 스트리밍 어댑터 메서드 1개 추가 |
| 저장소 | `app/infrastructure/persistence/json_store.JsonStore` | `JsonConversationRepository` 새로 |
| 도메인 | `Message` (`app/domain/chat.py`) | `Conversation` 엔티티 새로 (node 종속 X) |
| 로케일 | `JsonSettingsRepository` 그대로 | 없음 |
| 정적 자원 | 없음 | `chat_ui/static/{index.html, app.js, styles.css}` |
| 라우트 | 없음 | `chat_ui/routes.py` |

그래프용 `ChatThread`는 안 건드림. 새 `Conversation` 따로 둠.

---

## 2. 디렉토리 구조

```
chat_ui/
  __init__.py
  PLAN.md                       # 이 파일
  routes.py                     # Flask blueprint, /chat + /api/chat/*
  use_cases.py                  # 대화 CRUD + 스트리밍 송신
  domain.py                     # Conversation 엔티티
  repository.py                 # JsonConversationRepository (기존 JsonStore 위에)
  streaming.py                  # OpenAI 스트리밍 + TEST_MODE mock chunk
  static/
    index.html
    app.js
    styles.css
    vendor/
      marked.min.js             # 마크다운
      dompurify.min.js          # XSS 방지
```

---

## 3. 데이터 모델

`storage/data.json`에 새 키 `conversations` 추가. 그래프용 `nodes`/`edges`와 분리.

```jsonc
{
  "settings": { "locale": "ko" },        // 기존 공유
  "nodes": { ... },                       // 그래프용, 무관
  "edges": { ... },                       // 그래프용, 무관
  "threads": { ... },                     // 그래프 노드의 thread, 무관
  "messages": { ... },                    // 기존: thread_id로 묶임. 재사용 검토 필요
  "conversations": {                      // 신규
    "conv_xxx": {
      "id": "conv_xxx",
      "title": { "ko": "...", "en": "..." },
      "created_at": "...",
      "updated_at": "..."
    }
  }
}
```

**메시지 저장 결정 필요(❓):**
- 옵션 A: 기존 `messages` 테이블에 `thread_id = conversation_id`로 같이 저장.  → 코드 적게 추가, 그러나 그래프와 데이터 섞임.
- 옵션 B: 새 `chat_messages` 키 분리.  → 깔끔하지만 Repo 하나 더.

권장: **B (분리)**. 그래프 디버깅 시 데이터 섞이면 피곤함.

---

## 4. 백엔드 use case

`chat_ui/use_cases.py`:

- `ListConversationsUseCase.execute(locale) -> [Conversation]`
- `CreateConversationUseCase.execute(locale) -> Conversation`
- `RenameConversationUseCase.execute(id, locale, title)`
- `DeleteConversationUseCase.execute(id)`
- `LoadMessagesUseCase.execute(conversation_id) -> [Message]`
- `StreamReplyUseCase.execute(conversation_id, user_text, locale) -> Iterator[str]`
  - 사용자 메시지 저장
  - 시스템 프롬프트 + 최근 N개 메시지로 LLM 호출 (스트리밍)
  - 토큰 chunk를 yield
  - 끝나면 assistant 메시지 전체를 저장
  - 첫 메시지면 LLM으로 제목 생성 → 저장

시스템 프롬프트: 기존 graph용과 다르게 그래프 언급 X. "You are a helpful assistant. Respond primarily in {locale}."

---

## 5. 스트리밍

- 백엔드:
  - 신규 메서드 `StreamingChatModel.stream_reply(system_prompt, messages) -> Iterator[str]`
  - OpenAI: `client.chat.completions.create(stream=True)` 사용, `delta.content` yield
  - TEST_MODE / fallback: 결정적 응답 문자열을 8자 단위로 쪼개서 yield + 작은 sleep
- 라우트: Flask `Response(generator, mimetype="text/event-stream")`
  - 포맷: `data: <json>\n\n` 각 chunk마다, 끝에 `data: [DONE]\n\n`
- 프론트: `fetch` + `ReadableStream`, chunk 받을 때마다 message DOM에 append

---

## 6. 라우트 (blueprint `chat_ui`)

```
GET    /chat                                       # static index.html
GET    /api/chat/conversations                     # 목록
POST   /api/chat/conversations                     # 새 대화
PATCH  /api/chat/conversations/<id>                # 이름변경
DELETE /api/chat/conversations/<id>                # 삭제
GET    /api/chat/conversations/<id>/messages       # 메시지 로드
POST   /api/chat/conversations/<id>/messages       # SSE 스트리밍 응답
```

로케일은 기존 `POST /api/settings/locale` 그대로 사용. blueprint에서 추가 안 함.

---

## 7. 프론트엔드

`chat_ui/static/index.html`:

```
┌─────────────┬────────────────────────────────┐
│ sidebar     │ messages                       │
│             │                                │
│ [+ 새 대화] │ user / assistant 메시지 버블   │
│ 대화 1      │                                │
│ 대화 2 ⋯    │                                │
│ ...         ├────────────────────────────────┤
│             │ [textarea]            [전송]   │
│ [한/영]     │                                │
└─────────────┴────────────────────────────────┘
```

- 마크다운: `marked.parse(text)` → `DOMPurify.sanitize(...)` → innerHTML
- 코드블록: 초기엔 그냥 `<pre><code>` 스타일만. highlight.js는 나중.
- 스트리밍 중에는 매 chunk마다 raw 텍스트 append 후 마크다운 재렌더 (200ms throttle).
- 로케일: 기존 `i18n` 객체 패턴 참고.

---

## 8. 그래프 앱과 공존

- 기존 `composition_root.create_app(config)`에서 blueprint 추가 등록:
  ```python
  from chat_ui import register_chat_ui
  register_chat_ui(flask_app, settings_repository, llm_services)
  ```
- 기존 `/` 라우트는 그래프 UI 유지. `/chat`은 새 UI.
- 둘이 같은 `settings.locale` 공유. 한쪽에서 바꾸면 다른쪽도 영향.

---

## 9. 단계 (각 단계 끝마다 너 확인 필요)

1. **뼈대** — 디렉토리/빈 모듈/blueprint 등록. `/chat`에서 hello world.
2. **CRUD** — 대화 생성/목록/이름변경/삭제. 스트리밍 X, 마크다운 X.
3. **단순 채팅** — non-streaming으로 메시지 송신·응답·저장.
4. **스트리밍** — SSE + 프론트 ReadableStream. TEST_MODE chunk mock 포함.
5. **마크다운** — marked + DOMPurify 적용.
6. **한/영 토글 + 자동 제목** — locale 전환 + 첫 메시지로 대화 제목 생성.
7. **다듬기** — 키보드 단축키(Enter 전송, Shift+Enter 줄바꿈), 스크롤 자동 맨아래, 삭제 확인.

각 단계 전에 “1단계 시작?” 식으로 너에게 물어봄.

---

## 10. 결정 사항 (확정)

1. **메시지 저장**: 새 `chat_messages` 키로 분리.
2. **마크다운 라이브러리**: `static/vendor/`에 `marked.min.js` + `dompurify.min.js` 로컬 포함.
3. **LLM**: 일단 mock만 (TEST_MODE 경로). OpenAI 실호출은 나중.
4. **자동 제목**: ChatGPT 방식 — 첫 user 메시지 + 첫 assistant 응답을 LLM에게 주고 6~8 단어 요약 생성. TEST_MODE면 결정적 mock 제목.
5. **사이드바 UX**: 호버 시 ⋯ 버튼 → 이름변경/삭제 메뉴.

---

## 11. 안 할 것 (스코프 밖)

- 첨부 파일, 음성, 이미지
- 검색
- 폴더/태그
- 다중 사용자/인증
- 동시 대화 (한 번에 한 스트림)
- 토큰 카운터/비용 표시 (필요하면 나중에)
