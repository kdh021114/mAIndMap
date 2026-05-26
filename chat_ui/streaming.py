from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Iterator, List

from app.domain.chat import Message
from app.domain.ports import ChatModel
from app.infrastructure.llm.openai_client_factory import OpenAITextClient


class StreamingChatModel(ABC):
    @abstractmethod
    def stream_reply(
        self,
        *,
        system_prompt: str,
        messages: List[Message],
    ) -> Iterator[str]: ...


class MockStreamingChatModel(StreamingChatModel):
    """Wraps a synchronous ChatModel and yields the full reply in 8-char chunks."""

    def __init__(
        self,
        chat_model: ChatModel,
        chunk_size: int = 8,
        chunk_sleep: float = 0.03,
    ):
        self._chat_model = chat_model
        self._chunk_size = max(1, chunk_size)
        self._chunk_sleep = max(0.0, chunk_sleep)

    def stream_reply(
        self,
        *,
        system_prompt: str,
        messages: List[Message],
    ) -> Iterator[str]:
        full_text = self._chat_model.generate_reply(
            system_prompt=system_prompt,
            messages=messages,
        )
        for i in range(0, len(full_text), self._chunk_size):
            chunk = full_text[i : i + self._chunk_size]
            if self._chunk_sleep:
                time.sleep(self._chunk_sleep)
            yield chunk


class OpenAIStreamingChatModel(StreamingChatModel):
    """Skeleton for real OpenAI streaming.

    Intentionally not wired in Stage 4 (TEST_MODE is True). When implementing,
    use `client.responses.create(stream=True)` and yield event.delta-like text.
    See: https://platform.openai.com/docs/api-reference/responses-streaming
    """

    def __init__(self, text_client: OpenAITextClient, model_name: str):
        self._text_client = text_client
        self._model_name = model_name

    def stream_reply(
        self,
        *,
        system_prompt: str,
        messages: List[Message],
    ) -> Iterator[str]:
        raise NotImplementedError(
            "Wire OpenAI streaming in a later iteration. "
            "See https://platform.openai.com/docs/api-reference/responses-streaming"
        )
