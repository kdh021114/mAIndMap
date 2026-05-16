from __future__ import annotations

import re
from typing import List

from app.domain.chat import Message
from app.domain.ports import ChatModel, EdgePhraseGenerator, NodeTitleGenerator
from app.infrastructure.llm.openai_client_factory import OpenAITextClient


class OpenAIChatModel(ChatModel):
    def __init__(self, text_client: OpenAITextClient, model_name: str):
        self._text_client = text_client
        self._model_name = model_name

    def generate_reply(self, *, system_prompt: str, messages: List[Message]) -> str:
        input_text = self._format_messages(messages)
        reply = self._text_client.complete(
            model=self._model_name,
            instructions=system_prompt,
            input_text=input_text,
        )
        return reply or "I could not generate a response."

    def _format_messages(self, messages: List[Message]) -> str:
        lines = ["Current selected node conversation:"]
        lines.extend(f"{m.role}: {m.content}" for m in messages)
        lines.append("assistant:")
        return "\n".join(lines)


class OpenAINodeTitleGenerator(NodeTitleGenerator):
    def __init__(self, text_client: OpenAITextClient, model_name: str):
        self._text_client = text_client
        self._model_name = model_name

    def generate(self, *, first_user_prompt: str, locale: str) -> str:
        language = "Korean" if locale == "ko" else "English"
        instructions = (
            "Generate a concise chat-thread title for a graph node. "
            "The title should summarize the user's first prompt. "
            "Return only the title. No quotes, no bullets, no explanation. "
            f"Language: {language}. "
            "Length: Korean 3-8 eojeol, English 2-7 words."
        )
        title = self._text_client.complete(
            model=self._model_name,
            instructions=instructions,
            input_text=f"User's first prompt:\n{first_user_prompt}",
        )
        return self._clean_one_line(title, fallback="대화 요약" if locale == "ko" else "Conversation summary")

    def _clean_one_line(self, text: str, fallback: str) -> str:
        line = (text or "").strip().splitlines()[0].strip()
        line = re.sub(r'^["“”\'`]+|["“”\'`]+$', "", line).strip()
        return line[:80] or fallback


class OpenAIEdgePhraseGenerator(EdgePhraseGenerator):
    def __init__(self, text_client: OpenAITextClient, model_name: str):
        self._text_client = text_client
        self._model_name = model_name

    def generate(
        self,
        *,
        source_title: str,
        target_title: str,
        first_user_prompt: str,
        locale: str,
    ) -> str:
        language = "Korean" if locale == "ko" else "English"
        instructions = (
            "You generate a short phrase-level edge label for a tree-structured graph chat interface. "
            "The user already decided the graph structure. Do not propose nodes, edges, or graph edits. "
            "Describe the relationship from the parent node to the child node. "
            "Return exactly one short phrase. No quotes, no punctuation, no explanation. "
            f"Language: {language}. "
            "Length: Korean 2-5 eojeol, English 2-5 words."
        )
        input_text = (
            f"Parent node title: {source_title}\n"
            f"Child node title: {target_title}\n"
            f"Child node first user prompt: {first_user_prompt}\n"
            "Generate the edge phrase:"
        )
        phrase = self._text_client.complete(
            model=self._model_name,
            instructions=instructions,
            input_text=input_text,
        )
        return self._clean_phrase(phrase, fallback="구체화" if locale == "ko" else "Further detail")

    def _clean_phrase(self, text: str, fallback: str) -> str:
        line = (text or "").strip().splitlines()[0].strip()
        line = re.sub(r'^["“”\'`]+|["“”\'`]+$', "", line).strip()
        line = re.sub(r"[.!?。]+$", "", line).strip()
        return line[:60] or fallback
