from __future__ import annotations

from typing import List

from app.domain.chat import Message
from app.domain.ports import ChatModel, EdgePhraseGenerator, NodeTitleGenerator


class MockChatModel(ChatModel):
    def generate_reply(
        self,
        *,
        system_prompt: str,
        messages: List[Message],
        web_search_enabled: bool = False,
        truncation_notice: str | None = None,
    ) -> str:
        last_user = next((m for m in reversed(messages) if m.role == "user"), None)
        if last_user is None:
            return "무엇을 도와드릴까요?"
        search_note = " 웹검색 토글은 테스트 모드에서는 실제 검색을 호출하지 않습니다." if web_search_enabled else ""
        if any("Respond primarily in English" in system_prompt for _ in [0]):
            suffix = " Web search is not called in mock/test mode." if web_search_enabled else ""
            return f"Mock reply: I understand. Let's continue from: {last_user.content[:120]}{suffix}"
        return f"모의 응답: 이해했어. 이 방향으로 이어서 생각해보자: {last_user.content[:120]}{search_note}"


class MockNodeTitleGenerator(NodeTitleGenerator):
    def generate(self, *, first_user_prompt: str, locale: str) -> str:
        cleaned = " ".join(first_user_prompt.strip().split())
        if not cleaned:
            return "대화 요약" if locale == "ko" else "Conversation summary"
        words = cleaned.split()
        if locale == "ko":
            return " ".join(words[:6])[:40]
        return " ".join(words[:6]).title()[:50]


class MockEdgePhraseGenerator(EdgePhraseGenerator):
    def generate(
        self,
        *,
        source_title: str,
        target_title: str,
        first_user_prompt: str,
        locale: str,
    ) -> str:
        return "구체화" if locale == "ko" else "Further detail"
