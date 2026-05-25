from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, List

from app.domain.chat import Message
from app.domain.common import create_id
from app.domain.ports import ChatModel, NodeTitleGenerator
from chat_ui.domain import ChatMessage, Conversation
from chat_ui.repository import JsonConversationRepository
from chat_ui.streaming import StreamingChatModel

MAX_HISTORY = 20


def _build_system_prompt(locale: str) -> str:
    if locale == "ko":
        return "You are a helpful assistant. Respond primarily in Korean."
    return "You are a helpful assistant. Respond primarily in English."


def _to_domain_message(message: ChatMessage) -> Message:
    return Message(
        id=message.id,
        thread_id=message.conversation_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )


class ListConversationsUseCase:
    def __init__(self, conversation_repository: JsonConversationRepository):
        self._conversation_repository = conversation_repository

    def execute(self) -> List[Conversation]:
        return self._conversation_repository.list_conversations()


class CreateConversationUseCase:
    def __init__(self, conversation_repository: JsonConversationRepository):
        self._conversation_repository = conversation_repository

    def execute(self, *, locale: str) -> Conversation:
        return self._conversation_repository.create_conversation(locale=locale)


class RenameConversationUseCase:
    def __init__(self, conversation_repository: JsonConversationRepository):
        self._conversation_repository = conversation_repository

    def execute(self, *, conversation_id: str, locale: str, title: str) -> Conversation:
        cleaned = (title or "").strip()
        if not cleaned:
            raise ValueError("Title must not be empty.")
        return self._conversation_repository.rename_conversation(
            conversation_id=conversation_id,
            locale=locale,
            title=cleaned,
        )


class DeleteConversationUseCase:
    def __init__(self, conversation_repository: JsonConversationRepository):
        self._conversation_repository = conversation_repository

    def execute(self, *, conversation_id: str) -> None:
        self._conversation_repository.delete_conversation(conversation_id)


class LoadMessagesUseCase:
    def __init__(self, conversation_repository: JsonConversationRepository):
        self._conversation_repository = conversation_repository

    def execute(self, *, conversation_id: str) -> List[ChatMessage]:
        # Surfaces KeyError if the conversation is missing so routes can 404.
        self._conversation_repository.get_conversation(conversation_id)
        return self._conversation_repository.list_messages(conversation_id)


@dataclass(frozen=True)
class SendMessageResult:
    user: ChatMessage
    assistant: ChatMessage


class SendMessageUseCase:
    def __init__(
        self,
        conversation_repository: JsonConversationRepository,
        chat_model: ChatModel,
    ):
        self._conversation_repository = conversation_repository
        self._chat_model = chat_model

    def execute(
        self,
        *,
        conversation_id: str,
        user_text: str,
        locale: str,
    ) -> SendMessageResult:
        cleaned = (user_text or "").strip()
        if not cleaned:
            raise ValueError("Message content must not be empty.")
        # Triggers KeyError if missing so callers can map to 404.
        self._conversation_repository.get_conversation(conversation_id)

        user_message = ChatMessage.new(
            message_id=create_id("cmsg"),
            conversation_id=conversation_id,
            role="user",
            content=cleaned,
        )
        self._conversation_repository.add_message(user_message)

        history = self._conversation_repository.list_messages(conversation_id)[-MAX_HISTORY:]
        domain_messages = [_to_domain_message(m) for m in history]
        system_prompt = _build_system_prompt(locale)
        assistant_text = self._chat_model.generate_reply(
            system_prompt=system_prompt,
            messages=domain_messages,
        )

        assistant_message = ChatMessage.new(
            message_id=create_id("cmsg"),
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_text,
        )
        self._conversation_repository.add_message(assistant_message)

        return SendMessageResult(user=user_message, assistant=assistant_message)


class StreamReplyUseCase:
    """Stores the user message, streams the assistant reply, then stores it.

    Yields plain dicts; the route layer is responsible for SSE wire formatting.
    Frames:
      {"type": "user", "message": {...}}             -> once, before any chunk
      {"type": "chunk", "delta": "..."}              -> repeated
      {"type": "assistant", "message": {...}}        -> once, at the end
      {"type": "title", "conversationId", "title"}   -> at most once, after
                                                        "assistant", iff this
                                                        call was the very first
                                                        user message.
    """

    def __init__(
        self,
        conversation_repository: JsonConversationRepository,
        streaming_chat_model: StreamingChatModel,
        title_generator: NodeTitleGenerator,
    ):
        self._conversation_repository = conversation_repository
        self._streaming_chat_model = streaming_chat_model
        self._title_generator = title_generator

    def execute(
        self,
        *,
        conversation_id: str,
        user_text: str,
        locale: str,
    ) -> Iterator[dict]:
        cleaned = (user_text or "").strip()
        if not cleaned:
            raise ValueError("Message content must not be empty.")
        # Triggers KeyError if missing so the route can map to 404 before any
        # bytes are streamed back.
        self._conversation_repository.get_conversation(conversation_id)

        # Capture BEFORE persisting the new user message so the flag reflects
        # the conversation's prior state.
        is_first_user_message = (
            self._conversation_repository.count_user_messages(conversation_id) == 0
        )

        user_message = ChatMessage.new(
            message_id=create_id("cmsg"),
            conversation_id=conversation_id,
            role="user",
            content=cleaned,
        )
        self._conversation_repository.add_message(user_message)

        return self._stream(conversation_id, user_message, locale, is_first_user_message)

    def _stream(
        self,
        conversation_id: str,
        user_message: ChatMessage,
        locale: str,
        is_first_user_message: bool,
    ) -> Iterator[dict]:
        yield {
            "type": "user",
            "message": {
                "id": user_message.id,
                "role": user_message.role,
                "content": user_message.content,
                "createdAt": user_message.created_at,
            },
        }

        history = self._conversation_repository.list_messages(conversation_id)[-MAX_HISTORY:]
        domain_messages = [_to_domain_message(m) for m in history]
        system_prompt = _build_system_prompt(locale)

        buffer: List[str] = []
        for delta in self._streaming_chat_model.stream_reply(
            system_prompt=system_prompt,
            messages=domain_messages,
        ):
            if not delta:
                continue
            buffer.append(delta)
            yield {"type": "chunk", "delta": delta}

        assistant_message = ChatMessage.new(
            message_id=create_id("cmsg"),
            conversation_id=conversation_id,
            role="assistant",
            content="".join(buffer),
        )
        self._conversation_repository.add_message(assistant_message)

        yield {
            "type": "assistant",
            "message": {
                "id": assistant_message.id,
                "role": assistant_message.role,
                "content": assistant_message.content,
                "createdAt": assistant_message.created_at,
            },
        }

        if is_first_user_message:
            generated_title = self._maybe_generate_title(
                first_user_prompt=user_message.content,
                locale=locale,
            )
            if generated_title:
                try:
                    self._conversation_repository.set_conversation_title(
                        conversation_id=conversation_id,
                        locale=locale,
                        title=generated_title,
                    )
                    yield {
                        "type": "title",
                        "conversationId": conversation_id,
                        "title": generated_title,
                    }
                except Exception as exc:  # noqa: BLE001 — never break the stream
                    print(f"[chat_ui] failed to persist auto-title: {exc!r}")

    def _maybe_generate_title(self, *, first_user_prompt: str, locale: str) -> str:
        try:
            raw = self._title_generator.generate(
                first_user_prompt=first_user_prompt,
                locale=locale,
            )
        except Exception as exc:  # noqa: BLE001 — never break the stream
            print(f"[chat_ui] title generation failed: {exc!r}")
            return ""
        return (raw or "").strip()
