from __future__ import annotations

from typing import Any


class OpenAIClientFactory:
    """Factory for OpenAI SDK clients.

    Keeping this in one place makes it easy to later add organization IDs,
    project IDs, proxy settings, retries, tracing, or a different provider.
    """

    def __init__(self, api_key: str, timeout_seconds: float | None = None):
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._client = None

    def create(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "The openai package is not installed. Run: pip install -r requirements.txt"
                ) from exc
            client_kwargs = {"api_key": self._api_key}
            if self._timeout_seconds is not None:
                client_kwargs["timeout"] = self._timeout_seconds
            self._client = OpenAI(**client_kwargs)
        return self._client


class OpenAITextClient:
    def __init__(
        self,
        client_factory: OpenAIClientFactory,
        *,
        reasoning_effort: str | None = None,
        text_verbosity: str | None = None,
        store_responses: bool = False,
    ):
        self._client_factory = client_factory
        self._reasoning_effort = reasoning_effort
        self._text_verbosity = text_verbosity
        self._store_responses = store_responses

    def complete(
        self,
        *,
        model: str,
        instructions: str,
        input_text: str,
        max_output_tokens: int | None = None,
    ) -> str:
        client = self._client_factory.create()
        request: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": input_text,
            "store": self._store_responses,
        }
        if max_output_tokens is not None:
            request["max_output_tokens"] = max_output_tokens
        if self._reasoning_effort:
            request["reasoning"] = {"effort": self._reasoning_effort}
        if self._text_verbosity:
            request["text"] = {"verbosity": self._text_verbosity}

        response = client.responses.create(**request)
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
        # Defensive fallback for SDK shape changes.
        output = getattr(response, "output", []) or []
        chunks: list[str] = []
        for item in output:
            content = _read_field(item, "content", []) or []
            for part in content:
                part_text = _read_field(part, "text", None)
                if part_text:
                    chunks.append(part_text)
        return "\n".join(chunks).strip()


def _read_field(value: Any, field_name: str, default: Any) -> Any:
    if isinstance(value, dict):
        return value.get(field_name, default)
    return getattr(value, field_name, default)
