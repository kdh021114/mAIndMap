from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal

from app.domain.common import LocalizedText, utc_now_iso

MessageRole = Literal["user", "assistant", "system"]


@dataclass(frozen=True)
class ChatThread:
    id: str
    title: LocalizedText
    node_id: str
    created_at: str
    updated_at: str

    @staticmethod
    def new(thread_id: str, node_id: str, title: LocalizedText) -> "ChatThread":
        now = utc_now_iso()
        return ChatThread(
            id=thread_id,
            title=title,
            node_id=node_id,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def from_dict(data: dict) -> "ChatThread":
        return ChatThread(
            id=data["id"],
            title=dict(data.get("title", {})),
            node_id=data["node_id"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


@dataclass(frozen=True)
class Message:
    id: str
    thread_id: str
    role: MessageRole
    content: str
    created_at: str

    @staticmethod
    def new(message_id: str, thread_id: str, role: MessageRole, content: str) -> "Message":
        return Message(
            id=message_id,
            thread_id=thread_id,
            role=role,
            content=content,
            created_at=utc_now_iso(),
        )

    @staticmethod
    def from_dict(data: dict) -> "Message":
        return Message(
            id=data["id"],
            thread_id=data["thread_id"],
            role=data["role"],
            content=data["content"],
            created_at=data["created_at"],
        )


def messages_as_prompt_lines(messages: List[Message]) -> str:
    return "\n".join(f"{m.role}: {m.content}" for m in messages)
