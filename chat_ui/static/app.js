(() => {
  "use strict";

  const API = "/api/chat/conversations";
  const LOCALE_API = "/api/chat/locale";
  const SETTINGS_LOCALE_API = "/api/settings/locale";
  const STREAM_RENDER_INTERVAL_MS = 200;
  const SCROLL_PIN_THRESHOLD_PX = 80;
  const COMPOSER_MAX_LINES = 8;

  // i18n ----------------------------------------------------------------
  const SUPPORTED_LOCALES = ["ko", "en"];
  const I18N = {
    ko: {
      "app.title": "Chat",
      "sidebar.goGraph": "그래프 뷰",
      "sidebar.newChat": "+ 새 대화",
      "sidebar.localeToggle": "EN",
      "sidebar.empty": "+ 새 대화로 시작하세요",
      "chat.empty": "대화를 선택하세요",
      "chat.emptyMessages": "메시지를 입력해 대화를 시작하세요",
      "chat.placeholder": "메시지를 입력하세요",
      "composer.submit": "전송",
      "conv.untitled": "(제목 없음)",
      "menu.rename": "이름 변경",
      "menu.delete": "삭제",
      "menu.confirmDelete": "\"{title}\" 삭제할까요?",
      "menu.tooltip": "이름 변경 / 삭제",
      "menu.aria": "대화 메뉴 열기",
      "error.loadList": "대화 목록을 불러오지 못했습니다.",
      "error.stream": "오류: {message}",
    },
    en: {
      "app.title": "Chat",
      "sidebar.goGraph": "Graph View",
      "sidebar.newChat": "+ New chat",
      "sidebar.localeToggle": "KO",
      "sidebar.empty": "+ Start a new chat",
      "chat.empty": "Select a conversation",
      "chat.emptyMessages": "Type a message to start the conversation",
      "chat.placeholder": "Type a message",
      "composer.submit": "Send",
      "conv.untitled": "(untitled)",
      "menu.rename": "Rename",
      "menu.delete": "Delete",
      "menu.confirmDelete": "Delete \"{title}\"?",
      "menu.tooltip": "Rename / delete",
      "menu.aria": "Open conversation menu",
      "error.loadList": "Failed to load conversations.",
      "error.stream": "Error: {message}",
    },
  };

  function t(key, params) {
    const table = I18N[state.locale] || I18N.ko;
    let value = table[key];
    if (value == null) value = key;
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        value = value.replaceAll(`{${k}}`, String(v));
      }
    }
    return value;
  }

  function applyI18n() {
    document.documentElement.lang = state.locale;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (!key) return;
      const attr = el.getAttribute("data-i18n-attr");
      const value = t(key);
      if (attr) el.setAttribute(attr, value);
      else el.textContent = value;
    });
  }

  function resolveTitle(localizedTitle) {
    if (!localizedTitle || typeof localizedTitle !== "object") {
      return t("conv.untitled");
    }
    if (localizedTitle[state.locale]) return localizedTitle[state.locale];
    for (const loc of SUPPORTED_LOCALES) {
      if (loc !== state.locale && localizedTitle[loc]) return localizedTitle[loc];
    }
    return t("conv.untitled");
  }

  // markdown ------------------------------------------------------------
  if (typeof marked !== "undefined" && marked.setOptions) {
    marked.setOptions({ gfm: true, breaks: true });
  }

  function renderMarkdown(rawText) {
    const source = rawText || "";
    if (typeof marked === "undefined" || typeof DOMPurify === "undefined") {
      const div = document.createElement("div");
      div.textContent = source;
      return div.innerHTML;
    }
    const dirty = marked.parse(source);
    const clean = DOMPurify.sanitize(dirty);
    return hardenLinks(clean);
  }

  function hardenLinks(html) {
    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    const anchors = tpl.content.querySelectorAll("a");
    anchors.forEach((a) => {
      a.setAttribute("target", "_blank");
      a.setAttribute("rel", "noopener noreferrer");
    });
    const wrap = document.createElement("div");
    wrap.appendChild(tpl.content.cloneNode(true));
    return wrap.innerHTML;
  }

  function makeStreamRenderer(bubble) {
    let lastRunAt = 0;
    let pendingTimer = null;
    function flush() {
      lastRunAt = Date.now();
      pendingTimer = null;
      bubble.innerHTML = renderMarkdown(bubble.dataset.raw || "");
      scrollToBottomIfPinned(false);
    }
    function schedule() {
      const now = Date.now();
      const elapsed = now - lastRunAt;
      if (elapsed >= STREAM_RENDER_INTERVAL_MS) {
        if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
        flush();
      } else if (!pendingTimer) {
        pendingTimer = setTimeout(flush, STREAM_RENDER_INTERVAL_MS - elapsed);
      }
    }
    function finalize() {
      if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
      flush();
    }
    return { schedule, finalize };
  }

  // state ---------------------------------------------------------------
  const state = {
    locale: "ko",
    conversations: [],
    activeId: null,
    messages: [],
    sending: false,
    openMenuConvId: null,
    renamingConvId: null,
  };

  // dom -----------------------------------------------------------------
  const listEl = document.getElementById("conv-list");
  const listEmptyEl = document.getElementById("conv-list-empty");
  const newBtn = document.getElementById("new-conv-btn");
  const localeBtn = document.getElementById("locale-btn");
  const placeholderEl = document.getElementById("chat-placeholder");
  const messagesEl = document.getElementById("messages");
  const messagesEmptyEl = document.getElementById("messages-empty");
  const composerEl = document.getElementById("composer");
  const composerInput = document.getElementById("composer-input");
  const composerSubmit = document.getElementById("composer-submit");
  const menuEl = document.getElementById("conv-menu");

  // scroll helpers ------------------------------------------------------
  function isNearBottom() {
    return (
      messagesEl.scrollTop + messagesEl.clientHeight >=
      messagesEl.scrollHeight - SCROLL_PIN_THRESHOLD_PX
    );
  }

  function scrollToBottomIfPinned(force) {
    if (force || isNearBottom()) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  // composer auto-grow --------------------------------------------------
  function autosizeComposer() {
    composerInput.style.height = "auto";
    const cs = window.getComputedStyle(composerInput);
    const lineHeight = parseFloat(cs.lineHeight) || 20;
    const padTop = parseFloat(cs.paddingTop) || 0;
    const padBot = parseFloat(cs.paddingBottom) || 0;
    const borderTop = parseFloat(cs.borderTopWidth) || 0;
    const borderBot = parseFloat(cs.borderBottomWidth) || 0;
    const maxH = Math.round(
      lineHeight * COMPOSER_MAX_LINES + padTop + padBot + borderTop + borderBot,
    );
    const next = Math.min(composerInput.scrollHeight + borderTop + borderBot, maxH);
    composerInput.style.height = `${next}px`;
    composerInput.style.overflowY =
      composerInput.scrollHeight + borderTop + borderBot > maxH ? "auto" : "hidden";
  }

  // api -----------------------------------------------------------------
  async function fetchLocale() {
    const res = await fetch(LOCALE_API);
    if (!res.ok) throw new Error(`locale failed: ${res.status}`);
    return res.json();
  }

  async function postLocale(locale) {
    const res = await fetch(SETTINGS_LOCALE_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ locale }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `locale change failed: ${res.status}`);
    }
  }

  async function fetchConversations() {
    const res = await fetch(API);
    if (!res.ok) throw new Error(`list failed: ${res.status}`);
    return res.json();
  }

  async function createConversation() {
    const res = await fetch(API, { method: "POST" });
    if (!res.ok) throw new Error(`create failed: ${res.status}`);
    return res.json();
  }

  async function renameConversation(id, title) {
    const res = await fetch(`${API}/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `rename failed: ${res.status}`);
    }
    return res.json();
  }

  async function deleteConversation(id) {
    const res = await fetch(`${API}/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`delete failed: ${res.status}`);
  }

  async function fetchMessages(id) {
    const res = await fetch(`${API}/${encodeURIComponent(id)}/messages`);
    if (!res.ok) throw new Error(`messages failed: ${res.status}`);
    return res.json();
  }

  async function openMessageStream(id, content) {
    const res = await fetch(`${API}/${encodeURIComponent(id)}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || `send failed: ${res.status}`);
    }
    if (!res.body) throw new Error("streaming not supported");
    return res.body.getReader();
  }

  // render --------------------------------------------------------------
  function renderConversations() {
    listEl.innerHTML = "";
    for (const conv of state.conversations) {
      listEl.appendChild(buildConvItem(conv));
    }
    const empty = state.conversations.length === 0;
    listEmptyEl.hidden = !empty;
    listEl.hidden = empty;
  }

  function buildConvItem(conv) {
    const li = document.createElement("li");
    li.className = "conv-item" + (conv.id === state.activeId ? " active" : "");
    li.dataset.id = conv.id;

    const titleEl = document.createElement("span");
    titleEl.className = "conv-title";
    titleEl.textContent = resolveTitle(conv.title);

    const menuBtn = document.createElement("button");
    menuBtn.type = "button";
    menuBtn.className = "conv-menu-btn";
    menuBtn.textContent = "⋯";
    menuBtn.title = t("menu.tooltip");
    menuBtn.setAttribute("aria-label", t("menu.aria"));
    menuBtn.setAttribute("aria-haspopup", "menu");
    menuBtn.setAttribute("aria-expanded", "false");

    li.appendChild(titleEl);
    li.appendChild(menuBtn);

    if (state.renamingConvId === conv.id) {
      replaceTitleWithRenameInput(li, conv);
    }
    if (state.openMenuConvId === conv.id) {
      menuBtn.setAttribute("aria-expanded", "true");
    }

    return li;
  }

  function patchConvItemTitle(conversationId) {
    const li = listEl.querySelector(`li.conv-item[data-id="${CSS.escape(conversationId)}"]`);
    if (!li) return;
    const conv = state.conversations.find((c) => c.id === conversationId);
    if (!conv) return;
    if (state.renamingConvId === conversationId) return;
    const titleEl = li.querySelector(".conv-title");
    if (titleEl) titleEl.textContent = resolveTitle(conv.title);
  }

  function renderMessages() {
    messagesEl.innerHTML = "";
    for (const message of state.messages) {
      messagesEl.appendChild(buildMessageEl(message));
    }
    updateMessagesEmpty();
    scrollToBottomIfPinned(true);
  }

  function updateMessagesEmpty() {
    const hasActive = Boolean(state.activeId);
    const empty = hasActive && state.messages.length === 0 && !state.sending;
    messagesEmptyEl.hidden = !empty;
  }

  function buildMessageEl(message) {
    const wrap = document.createElement("div");
    wrap.className = `message ${message.role}`;

    const roleEl = document.createElement("div");
    roleEl.className = "message-role";
    roleEl.textContent = message.role;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";
    bubble.dataset.raw = message.content || "";
    bubble.innerHTML = renderMarkdown(message.content);

    wrap.appendChild(roleEl);
    wrap.appendChild(bubble);
    return wrap;
  }

  function renderChatPane() {
    const hasActive = Boolean(state.activeId);
    placeholderEl.hidden = hasActive;
    messagesEl.hidden = !hasActive;
    composerEl.hidden = !hasActive;
    if (!hasActive) {
      placeholderEl.textContent = t("chat.empty");
      messagesEl.innerHTML = "";
      composerInput.value = "";
      autosizeComposer();
      messagesEmptyEl.hidden = true;
    } else {
      updateMessagesEmpty();
    }
    updateComposerEnabled();
  }

  function updateComposerEnabled() {
    const hasActive = Boolean(state.activeId);
    composerSubmit.disabled = state.sending || !hasActive || !composerInput.value.trim();
    composerInput.disabled = state.sending || !hasActive;
    composerEl.classList.toggle("is-sending", state.sending);
  }

  function render() {
    renderConversations();
    renderChatPane();
  }

  // inline rename -------------------------------------------------------
  function replaceTitleWithRenameInput(li, conv) {
    const titleEl = li.querySelector(".conv-title");
    if (!titleEl) return;
    const displayTitle = resolveTitle(conv.title);
    const input = document.createElement("input");
    input.type = "text";
    input.className = "conv-rename-input";
    input.value = displayTitle;
    input.dataset.convId = conv.id;
    input.dataset.originalTitle = displayTitle;
    titleEl.replaceWith(input);
    requestAnimationFrame(() => {
      input.focus();
      input.select();
    });
  }

  function startRename(convId) {
    closeMenu();
    state.renamingConvId = convId;
    const li = listEl.querySelector(`li.conv-item[data-id="${CSS.escape(convId)}"]`);
    if (!li) return;
    const conv = state.conversations.find((c) => c.id === convId);
    if (!conv) return;
    replaceTitleWithRenameInput(li, conv);
  }

  function cancelRename() {
    const convId = state.renamingConvId;
    if (!convId) return;
    state.renamingConvId = null;
    const li = listEl.querySelector(`li.conv-item[data-id="${CSS.escape(convId)}"]`);
    if (!li) return;
    const input = li.querySelector(".conv-rename-input");
    if (!input) return;
    const original = input.dataset.originalTitle || "";
    const span = document.createElement("span");
    span.className = "conv-title";
    span.textContent = original;
    input.replaceWith(span);
  }

  async function commitRename(input) {
    const convId = input.dataset.convId;
    const original = input.dataset.originalTitle || "";
    const next = input.value.trim();
    state.renamingConvId = null;

    if (!next || next === original) {
      const span = document.createElement("span");
      span.className = "conv-title";
      span.textContent = original;
      input.replaceWith(span);
      return;
    }

    // Optimistic swap.
    const span = document.createElement("span");
    span.className = "conv-title";
    span.textContent = next;
    input.replaceWith(span);

    try {
      await renameConversation(convId, next);
      const conv = state.conversations.find((c) => c.id === convId);
      if (conv) {
        conv.title = { ...(conv.title || {}), [state.locale]: next };
      }
    } catch (err) {
      window.alert(err.message);
      span.textContent = original;
    }
  }

  // menu ----------------------------------------------------------------
  function openMenu(convId, anchorBtn) {
    if (state.openMenuConvId === convId) {
      closeMenu();
      return;
    }
    closeMenu();
    state.openMenuConvId = convId;
    menuEl.dataset.convId = convId;
    menuEl.hidden = false;
    anchorBtn.setAttribute("aria-expanded", "true");

    // Position next to the anchor.
    const rect = anchorBtn.getBoundingClientRect();
    menuEl.style.visibility = "hidden";
    menuEl.style.left = "0px";
    menuEl.style.top = "0px";
    const menuRect = menuEl.getBoundingClientRect();
    let left = rect.right + 4;
    let top = rect.top;
    if (left + menuRect.width > window.innerWidth - 8) {
      left = Math.max(8, rect.left - menuRect.width - 4);
    }
    if (top + menuRect.height > window.innerHeight - 8) {
      top = Math.max(8, window.innerHeight - menuRect.height - 8);
    }
    menuEl.style.left = `${left}px`;
    menuEl.style.top = `${top}px`;
    menuEl.style.visibility = "";
  }

  function closeMenu() {
    if (state.openMenuConvId == null) return;
    const id = state.openMenuConvId;
    state.openMenuConvId = null;
    menuEl.hidden = true;
    delete menuEl.dataset.convId;
    const btn = listEl.querySelector(
      `li.conv-item[data-id="${CSS.escape(id)}"] .conv-menu-btn`,
    );
    if (btn) btn.setAttribute("aria-expanded", "false");
  }

  async function handleMenuAction(action) {
    const convId = menuEl.dataset.convId;
    if (!convId) return;
    const conv = state.conversations.find((c) => c.id === convId);
    closeMenu();
    if (!conv) return;
    if (action === "rename") {
      startRename(convId);
    } else if (action === "delete") {
      const displayTitle = resolveTitle(conv.title);
      if (!window.confirm(t("menu.confirmDelete", { title: displayTitle }))) return;
      try {
        await deleteConversation(convId);
        if (state.activeId === convId) {
          state.activeId = null;
          state.messages = [];
          messagesEl.innerHTML = "";
        }
        await reload();
      } catch (err) {
        window.alert(err.message);
      }
    }
  }

  // actions -------------------------------------------------------------
  async function selectConversation(id) {
    if (state.activeId === id) return;
    state.activeId = id;
    state.messages = [];
    render();
    try {
      state.messages = await fetchMessages(id);
    } catch (err) {
      console.error(err);
      window.alert(err.message);
      return;
    }
    if (state.activeId !== id) return;
    renderMessages();
    scrollToBottomIfPinned(true);
  }

  async function reload() {
    state.conversations = await fetchConversations();
    render();
    if (state.activeId) renderMessages();
  }

  function appendMessageToDom(message, { streaming = false } = {}) {
    const el = buildMessageEl(message);
    if (streaming) el.querySelector(".message-bubble").classList.add("streaming");
    messagesEl.appendChild(el);
    updateMessagesEmpty();
    scrollToBottomIfPinned(true);
    return el;
  }

  async function consumeStream(reader, handlers) {
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const frame = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const line = frame.startsWith("data: ") ? frame.slice(6) : frame.trim();
        if (!line) continue;
        if (line === "[DONE]") {
          handlers.onDone();
          return;
        }
        let payload;
        try { payload = JSON.parse(line); } catch (e) { continue; }
        handlers.onFrame(payload);
      }
    }
    handlers.onDone();
  }

  async function submitMessage() {
    if (state.sending || !state.activeId) return;
    const content = composerInput.value;
    if (!content.trim()) return;
    state.sending = true;
    updateComposerEnabled();
    const conversationId = state.activeId;

    const optimisticUser = {
      id: `__pending_user_${Date.now()}`,
      role: "user",
      content: content,
      createdAt: new Date().toISOString(),
    };
    let userEl = null;
    let assistantEl = null;
    let assistantBubble = null;
    let assistantRenderer = null;

    if (state.activeId === conversationId) {
      composerInput.value = "";
      autosizeComposer();
      userEl = appendMessageToDom(optimisticUser);
      scrollToBottomIfPinned(true);
    }

    let streamError = null;
    try {
      const reader = await openMessageStream(conversationId, content);
      await consumeStream(reader, {
        onFrame: (payload) => {
          if (state.activeId !== conversationId && payload.type !== "title") return;
          if (payload.type === "user") {
            const real = payload.message;
            if (userEl) {
              const newEl = buildMessageEl(real);
              userEl.replaceWith(newEl);
              userEl = newEl;
            } else {
              userEl = appendMessageToDom(real);
            }
            assistantEl = appendMessageToDom(
              { id: "__pending_assistant", role: "assistant", content: "" },
              { streaming: true },
            );
            assistantBubble = assistantEl.querySelector(".message-bubble");
            assistantBubble.dataset.raw = "";
            assistantRenderer = makeStreamRenderer(assistantBubble);
            scrollToBottomIfPinned(true);
          } else if (payload.type === "chunk") {
            if (!assistantBubble) return;
            assistantBubble.dataset.raw =
              (assistantBubble.dataset.raw || "") + (payload.delta || "");
            assistantRenderer.schedule();
          } else if (payload.type === "assistant") {
            if (assistantRenderer) assistantRenderer.finalize();
            const real = payload.message;
            if (assistantEl) {
              const finalEl = buildMessageEl(real);
              assistantEl.replaceWith(finalEl);
              assistantEl = finalEl;
              assistantBubble = null;
              assistantRenderer = null;
            } else {
              appendMessageToDom(real);
            }
            scrollToBottomIfPinned(true);
          } else if (payload.type === "title") {
            const cid = payload.conversationId;
            const conv = state.conversations.find((c) => c.id === cid);
            if (conv) {
              conv.title = { ...(conv.title || {}), [state.locale]: payload.title };
              patchConvItemTitle(cid);
            }
          }
        },
        onDone: () => {
          if (assistantRenderer) assistantRenderer.finalize();
        },
      });
    } catch (err) {
      streamError = err;
    }

    if (state.activeId === conversationId) {
      if (streamError) {
        if (assistantBubble) {
          assistantBubble.classList.remove("streaming");
          assistantBubble.dataset.raw = t("error.stream", { message: streamError.message });
          assistantBubble.innerHTML = renderMarkdown(assistantBubble.dataset.raw);
        } else if (userEl) {
          appendMessageToDom({
            id: "__error",
            role: "assistant",
            content: t("error.stream", { message: streamError.message }),
          });
        }
      }
      try {
        state.messages = await fetchMessages(conversationId);
      } catch (e) { /* non-fatal */ }
    }

    try {
      state.conversations = await fetchConversations();
      renderConversations();
    } catch (e) { /* non-fatal */ }

    state.sending = false;
    updateComposerEnabled();
    updateMessagesEmpty();
    composerInput.focus();
  }

  async function toggleLocale() {
    const target = state.locale === "ko" ? "en" : "ko";
    try {
      await postLocale(target);
    } catch (err) {
      window.alert(err.message);
      return;
    }
    state.locale = target;
    applyI18n();
    renderConversations();
    renderChatPane();
  }

  // event wiring (bound once at boot, delegated where possible) ---------
  newBtn.addEventListener("click", async () => {
    closeMenu();
    try {
      const created = await createConversation();
      state.activeId = created.id;
      state.messages = [];
      await reload();
      composerInput.focus();
    } catch (err) {
      window.alert(err.message);
    }
  });

  localeBtn.addEventListener("click", () => {
    if (state.sending) return;
    toggleLocale();
  });

  composerEl.addEventListener("submit", (e) => {
    e.preventDefault();
    submitMessage();
  });

  composerInput.addEventListener("input", () => {
    autosizeComposer();
    updateComposerEnabled();
  });

  composerInput.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    // Cmd/Ctrl+Enter or plain Enter (without Shift) submits.
    if (e.shiftKey) return; // newline
    if (e.isComposing || e.keyCode === 229) return; // IME composition
    e.preventDefault();
    if (state.sending || !state.activeId) return;
    if (!composerInput.value.trim()) return;
    submitMessage();
  });

  // Delegated handlers on the list (bound once).
  listEl.addEventListener("click", (e) => {
    const menuBtn = e.target.closest(".conv-menu-btn");
    if (menuBtn) {
      e.stopPropagation();
      const li = menuBtn.closest(".conv-item");
      if (li) openMenu(li.dataset.id, menuBtn);
      return;
    }
    if (e.target.closest(".conv-rename-input")) return;
    const li = e.target.closest(".conv-item");
    if (!li) return;
    selectConversation(li.dataset.id);
  });

  listEl.addEventListener("keydown", (e) => {
    const input = e.target.closest(".conv-rename-input");
    if (!input) return;
    if (e.key === "Enter") {
      e.preventDefault();
      commitRename(input);
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelRename();
    }
  });

  listEl.addEventListener("focusout", (e) => {
    const input = e.target.closest && e.target.closest(".conv-rename-input");
    if (!input) return;
    // Avoid double-commit if Enter already cleared state.
    if (state.renamingConvId !== input.dataset.convId) return;
    commitRename(input);
  });

  menuEl.addEventListener("click", (e) => {
    const item = e.target.closest(".conv-menu-item");
    if (!item) return;
    e.stopPropagation();
    handleMenuAction(item.dataset.action);
  });

  // Outside click closes menu. Single bound listener on document.
  document.addEventListener("mousedown", (e) => {
    if (state.openMenuConvId == null) return;
    if (menuEl.contains(e.target)) return;
    if (e.target.closest(".conv-menu-btn")) return;
    closeMenu();
  });

  // Global Esc: close menu first, then cancel rename.
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (state.openMenuConvId != null) {
      closeMenu();
      e.preventDefault();
      return;
    }
    if (state.renamingConvId != null) {
      cancelRename();
      e.preventDefault();
    }
  });

  window.addEventListener("resize", () => {
    if (state.openMenuConvId != null) closeMenu();
  });

  // boot ----------------------------------------------------------------
  (async () => {
    try {
      const { locale } = await fetchLocale();
      if (SUPPORTED_LOCALES.includes(locale)) state.locale = locale;
    } catch (err) {
      console.warn("locale fetch failed; defaulting", err);
    }
    applyI18n();
    autosizeComposer();
    try {
      await reload();
    } catch (err) {
      console.error(err);
      placeholderEl.textContent = t("error.loadList");
    }
  })();
})();
