from __future__ import annotations

from dataclasses import dataclass

from app.domain.ports import ChatModel, EdgePhraseGenerator, NodeTitleGenerator
from app.infrastructure.llm.fallback_models import (
    MockChatModel,
    MockEdgePhraseGenerator,
    MockNodeTitleGenerator,
)
from app.infrastructure.llm.openai_client_factory import OpenAIClientFactory, OpenAITextClient
from app.infrastructure.llm.openai_models import (
    OpenAIChatModel,
    OpenAIEdgePhraseGenerator,
    OpenAINodeTitleGenerator,
)


@dataclass(frozen=True)
class LlmConfig:
    api_key: str
    chat_model: str
    edge_model: str
    title_model: str
    reasoning_effort: str | None
    text_verbosity: str | None
    chat_max_output_tokens: int | None
    label_max_output_tokens: int | None
    store_responses: bool
    timeout_seconds: float | None
    web_search_enabled: bool
    web_search_context_size: str
    web_search_max_tool_calls: int | None
    web_search_tool_choice: str | None
    web_search_external_access: bool
    use_mock_when_no_api_key: bool
    test_mode: bool


@dataclass(frozen=True)
class LlmServices:
    chat_model: ChatModel
    edge_phrase_generator: EdgePhraseGenerator
    title_generator: NodeTitleGenerator
    mode: str  # "test", "mock", or "openai"
    web_search_available: bool

    @property
    def using_mock(self) -> bool:
        return self.mode in {"test", "mock"}


class LlmProviderFactory:
    """Composition factory for LLM-related services.

    Application use cases depend on ChatModel, NodeTitleGenerator, and
    EdgePhraseGenerator interfaces. This factory is the only place that decides
    whether to inject OpenAI implementations or deterministic local doubles.
    """

    def __init__(self, config: LlmConfig):
        self._config = config

    def create_services(self) -> LlmServices:
        if self._config.test_mode:
            return self._create_local_services(mode="test")

        if not self._config.api_key:
            if self._config.use_mock_when_no_api_key:
                return self._create_local_services(mode="mock")
            raise RuntimeError("OPENAI_API_KEY is missing. Add it to .env or enable TEST_MODE in config.py.")

        client_factory = OpenAIClientFactory(
            api_key=self._config.api_key,
            timeout_seconds=self._config.timeout_seconds,
        )
        text_client = OpenAITextClient(
            client_factory,
            reasoning_effort=self._config.reasoning_effort,
            text_verbosity=self._config.text_verbosity,
            store_responses=self._config.store_responses,
        )
        return LlmServices(
            chat_model=OpenAIChatModel(
                text_client,
                self._config.chat_model,
                max_output_tokens=self._config.chat_max_output_tokens,
                web_search_enabled=self._config.web_search_enabled,
                web_search_context_size=self._config.web_search_context_size,
                web_search_max_tool_calls=self._config.web_search_max_tool_calls,
                web_search_tool_choice=self._config.web_search_tool_choice,
                web_search_external_access=self._config.web_search_external_access,
            ),
            edge_phrase_generator=OpenAIEdgePhraseGenerator(
                text_client,
                self._config.edge_model,
                max_output_tokens=self._config.label_max_output_tokens,
            ),
            title_generator=OpenAINodeTitleGenerator(
                text_client,
                self._config.title_model,
                max_output_tokens=self._config.label_max_output_tokens,
            ),
            mode="openai",
            web_search_available=self._config.web_search_enabled,
        )

    def _create_local_services(self, *, mode: str) -> LlmServices:
        return LlmServices(
            chat_model=MockChatModel(),
            edge_phrase_generator=MockEdgePhraseGenerator(),
            title_generator=MockNodeTitleGenerator(),
            mode=mode,
            web_search_available=False,
        )
