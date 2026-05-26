from __future__ import annotations

from dataclasses import asdict
from typing import Iterable, List, Optional

from app.domain.common import LocalizedText, create_id, utc_now_iso
from app.infrastructure.persistence.json_store import JsonStore
from chat_ui.domain import ChatMessage, Conversation


DEFAULT_TITLE: LocalizedText = {"ko": "새 대화", "en": "New chat"}
SUPPORTED_LOCALES: tuple[str, ...] = ("ko", "en")


class JsonConversationRepository:
    """Stores conversations and their messages.

    Uses two separate top-level keys (`conversations`, `chat_messages`) so the
    graph-side data shape stays untouched. Both default to {} when missing.
    """

    def __init__(self, store: JsonStore):
        self._store = store

    def list_conversations(self) -> List[Conversation]:
        state = self._store.read()
        raw = state.get("conversations", {})
        conversations = [Conversation.from_dict(v) for v in raw.values()]
        return sorted(conversations, key=lambda c: c.updated_at, reverse=True)

    def get_conversation(self, conversation_id: str) -> Conversation:
        state = self._store.read()
        raw = state.get("conversations", {})
        try:
            return Conversation.from_dict(raw[conversation_id])
        except KeyError as exc:
            raise KeyError(f"Conversation not found: {conversation_id}") from exc

    def create_conversation(
        self,
        locale: str,
        title: Optional[LocalizedText] = None,
    ) -> Conversation:
        resolved_title = dict(title) if title else dict(DEFAULT_TITLE)
        conversation = Conversation.new(create_id("conv"), resolved_title)

        def mutate(state: dict) -> None:
            state.setdefault("conversations", {})[conversation.id] = asdict(conversation)

        self._store.update(mutate)
        return conversation

    def rename_conversation(
        self,
        conversation_id: str,
        locale: str,
        title: str,
    ) -> Conversation:
        updated_at = utc_now_iso()

        def mutate(state: dict) -> None:
            bucket = state.setdefault("conversations", {})
            if conversation_id not in bucket:
                raise KeyError(f"Conversation not found: {conversation_id}")
            entry = bucket[conversation_id]
            entry.setdefault("title", {})[locale] = title
            entry["updated_at"] = updated_at

        self._store.update(mutate)
        return self.get_conversation(conversation_id)

    def set_conversation_title(
        self,
        conversation_id: str,
        locale: str,
        title: str,
    ) -> Conversation:
        if locale not in SUPPORTED_LOCALES:
            raise ValueError(f"Unsupported locale: {locale}")
        cleaned = (title or "").strip()
        if not cleaned:
            raise ValueError("Title must not be empty.")
        updated_at = utc_now_iso()

        def mutate(state: dict) -> None:
            bucket = state.setdefault("conversations", {})
            if conversation_id not in bucket:
                raise KeyError(f"Conversation not found: {conversation_id}")
            entry = bucket[conversation_id]
            entry.setdefault("title", {})[locale] = cleaned
            entry["updated_at"] = updated_at

        self._store.update(mutate)
        return self.get_conversation(conversation_id)

    def delete_conversation(self, conversation_id: str) -> None:
        def mutate(state: dict) -> None:
            bucket = state.setdefault("conversations", {})
            if conversation_id not in bucket:
                raise KeyError(f"Conversation not found: {conversation_id}")
            bucket.pop(conversation_id, None)
            messages = state.setdefault("chat_messages", {})
            for message_id in [
                mid
                for mid, payload in messages.items()
                if payload.get("conversation_id") == conversation_id
            ]:
                messages.pop(message_id, None)

        self._store.update(mutate)

    def touch_conversation(self, conversation_id: str) -> None:
        updated_at = utc_now_iso()

        def mutate(state: dict) -> None:
            bucket = state.setdefault("conversations", {})
            if conversation_id not in bucket:
                raise KeyError(f"Conversation not found: {conversation_id}")
            bucket[conversation_id]["updated_at"] = updated_at

        self._store.update(mutate)

    def count_user_messages(self, conversation_id: str) -> int:
        state = self._store.read()
        raw = state.get("chat_messages", {})
        return sum(
            1
            for payload in raw.values()
            if payload.get("conversation_id") == conversation_id
            and payload.get("role") == "user"
        )

    def list_messages(self, conversation_id: str) -> List[ChatMessage]:
        state = self._store.read()
        raw = state.get("chat_messages", {})
        messages = [
            ChatMessage.from_dict(payload)
            for payload in raw.values()
            if payload.get("conversation_id") == conversation_id
        ]
        return sorted(messages, key=lambda m: m.created_at)

    def add_message(self, message: ChatMessage) -> ChatMessage:
        def mutate(state: dict) -> None:
            conversations = state.setdefault("conversations", {})
            if message.conversation_id not in conversations:
                raise KeyError(
                    f"Conversation not found: {message.conversation_id}"
                )
            state.setdefault("chat_messages", {})[message.id] = asdict(message)
            conversations[message.conversation_id]["updated_at"] = message.created_at

        self._store.update(mutate)
        return message
