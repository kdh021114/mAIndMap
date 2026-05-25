from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.common import LocalizedText, utc_now_iso

ChatMessageRole = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class Conversation:
    id: str
    title: LocalizedText
    created_at: str
    updated_at: str

    @staticmethod
    def new(conversation_id: str, title: LocalizedText) -> "Conversation":
        now = utc_now_iso()
        return Conversation(
            id=conversation_id,
            title=title,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def from_dict(data: dict) -> "Conversation":
        return Conversation(
            id=data["id"],
            title=dict(data.get("title", {})),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class ChatMessage:
    id: str
    conversation_id: str
    role: ChatMessageRole
    content: str
    created_at: str

    @staticmethod
    def new(
        message_id: str,
        conversation_id: str,
        role: ChatMessageRole,
        content: str,
    ) -> "ChatMessage":
        return ChatMessage(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=utc_now_iso(),
        )

    @staticmethod
    def from_dict(data: dict) -> "ChatMessage":
        return ChatMessage(
            id=data["id"],
            conversation_id=data["conversation_id"],
            role=data["role"],
            content=data["content"],
            created_at=data["created_at"],
        )
