from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.application.localization import pick_localized_text
from app.domain.ports import ChatRepository, GraphRepository, SettingsRepository


SNIPPET_PADDING = 40
SNIPPET_MAX_LENGTH = 160


@dataclass(frozen=True)
class SearchMatch:
    type: str  # "title" | "message"
    snippet: str
    message_id: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class SearchResult:
    node_id: str
    node_title: str
    thread_id: str
    matches: List[SearchMatch]


class SearchWorkspaceUseCase:
    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        settings_repository: SettingsRepository,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._settings_repository = settings_repository

    def execute(self, *, query: str) -> List[dict]:
        query = (query or "").strip()
        if not query:
            return []
        needle = query.lower()
        locale = self._settings_repository.get_locale()
        graph_thread_id = self._settings_repository.get_active_graph_thread_id()
        nodes = self._graph_repository.list_nodes(graph_thread_id=graph_thread_id)

        results: List[dict] = []
        for node in nodes:
            display_title = pick_localized_text(node.title, locale, fallback="Untitled")
            matches: List[SearchMatch] = []

            if needle in display_title.lower():
                matches.append(
                    SearchMatch(
                        type="title",
                        snippet=_build_snippet(display_title, needle),
                    )
                )

            for message in self._chat_repository.list_messages(node.thread_id):
                if needle in (message.content or "").lower():
                    matches.append(
                        SearchMatch(
                            type="message",
                            snippet=_build_snippet(message.content, needle),
                            message_id=message.id,
                            role=message.role,
                        )
                    )

            if matches:
                results.append(
                    {
                        "nodeId": node.id,
                        "nodeTitle": display_title,
                        "threadId": node.thread_id,
                        "matches": [
                            {
                                "type": m.type,
                                "snippet": m.snippet,
                                "messageId": m.message_id,
                                "role": m.role,
                            }
                            for m in matches
                        ],
                    }
                )

        return results


def _build_snippet(text: str, needle: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    index = lowered.find(needle)
    if index < 0:
        return text[:SNIPPET_MAX_LENGTH]
    start = max(0, index - SNIPPET_PADDING)
    end = min(len(text), index + len(needle) + SNIPPET_PADDING)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet[:SNIPPET_MAX_LENGTH]
