from __future__ import annotations

from typing import Any


class OpenAIClientFactory:
    """Factory for OpenAI SDK clients.

    Keeping this in one place makes it easy to later add organization IDs,
    project IDs, proxy settings, retries, tracing, or a different provider.
    """

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None

    def create(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "The openai package is not installed. Run: pip install -r requirements.txt"
                ) from exc
            self._client = OpenAI(api_key=self._api_key)
        return self._client


class OpenAITextClient:
    def __init__(self, client_factory: OpenAIClientFactory):
        self._client_factory = client_factory

    def complete(self, *, model: str, instructions: str, input_text: str) -> str:
        client = self._client_factory.create()
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=input_text,
        )
        text = getattr(response, "output_text", None)
        if text:
            return text.strip()
        # Defensive fallback for SDK shape changes.
        output = getattr(response, "output", []) or []
        chunks: list[str] = []
        for item in output:
            content = getattr(item, "content", []) or []
            for part in content:
                part_text = getattr(part, "text", None)
                if part_text:
                    chunks.append(part_text)
        return "\n".join(chunks).strip()
