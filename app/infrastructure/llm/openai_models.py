from __future__ import annotations

import re
from typing import List

from app.domain.chat import Message
from app.domain.ports import ChatModel, EdgePhraseGenerator, NodeTitleGenerator
from app.infrastructure.llm.openai_client_factory import OpenAITextClient


class OpenAIChatModel(ChatModel):
    def __init__(
        self,
        text_client: OpenAITextClient,
        model_name: str,
        *,
        max_output_tokens: int | None,
        web_search_enabled: bool,
        web_search_context_size: str,
        web_search_max_tool_calls: int | None,
        web_search_tool_choice: str | None,
        web_search_external_access: bool,
    ):
        self._text_client = text_client
        self._model_name = model_name
        self._max_output_tokens = max_output_tokens
        self._web_search_enabled = web_search_enabled
        self._web_search_context_size = web_search_context_size
        self._web_search_max_tool_calls = web_search_max_tool_calls
        self._web_search_tool_choice = web_search_tool_choice
        self._web_search_external_access = web_search_external_access

    def generate_reply(
        self,
        *,
        system_prompt: str,
        messages: List[Message],
        web_search_enabled: bool = False,
        truncation_notice: str | None = None,
    ) -> str:
        input_text = self._format_messages(messages)
        reply = self._text_client.complete(
            model=self._model_name,
            instructions=system_prompt,
            input_text=input_text,
            max_output_tokens=self._max_output_tokens,
            web_search_options=self._web_search_options(web_search_enabled),
            truncation_notice=truncation_notice,
        )
        return reply or "I could not generate a response."

    def _web_search_options(self, requested: bool) -> dict | None:
        if not requested or not self._web_search_enabled:
            return None
        return {
            "search_context_size": self._web_search_context_size,
            "max_tool_calls": self._web_search_max_tool_calls,
            "tool_choice": self._web_search_tool_choice,
            "external_web_access": self._web_search_external_access,
        }

    def _format_messages(self, messages: List[Message]) -> str:
        lines = ["Current selected node conversation:"]
        lines.extend(f"{m.role}: {m.content}" for m in messages)
        lines.append("assistant:")
        return "\n".join(lines)


class OpenAINodeTitleGenerator(NodeTitleGenerator):
    def __init__(
        self,
        text_client: OpenAITextClient,
        model_name: str,
        *,
        max_output_tokens: int | None,
    ):
        self._text_client = text_client
        self._model_name = model_name
        self._max_output_tokens = max_output_tokens

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
            max_output_tokens=self._max_output_tokens,
        )
        return self._clean_one_line(title, fallback="대화 요약" if locale == "ko" else "Conversation summary")

    def _clean_one_line(self, text: str, fallback: str) -> str:
        line = (text or "").strip().splitlines()[0].strip()
        line = re.sub(r'^["“”\'`]+|["“”\'`]+$', "", line).strip()
        return line[:80] or fallback


class OpenAIEdgePhraseGenerator(EdgePhraseGenerator):
    def __init__(
        self,
        text_client: OpenAITextClient,
        model_name: str,
        *,
        max_output_tokens: int | None,
    ):
        self._text_client = text_client
        self._model_name = model_name
        self._max_output_tokens = max_output_tokens

    def generate(
        self,
        *,
        source_title: str,
        target_title: str,
        first_user_prompt: str,
        locale: str,
    ) -> str:
        language = "Korean" if locale == "ko" else "English"
        allowed_labels = (
            "구체화, 원인, 결과, 비교, 대안, 조건, 조건 확인, 근거, 검증, 반례, 보완, 분해, 후속 질문"
            if locale == "ko"
            else "Specific detail, Cause, Result, Comparison, Alternative, Condition, Condition check, Evidence, Verification, Counterexample, Supplement, Breakdown, Follow-up"
        )
        specific_detail_label = "구체화" if locale == "ko" else "Specific detail"
        bad_examples = (
            "Bad labels: 관광지 추천 안내, 인터넷 검색 가능 여부, 싱가포르 여행. "
            "Good labels: 구체화, 검증, 비교."
            if locale == "ko"
            else "Bad labels: Tourist recommendations, Internet search availability, Singapore trip. "
            "Good labels: Specific detail, Verification, Comparison."
        )
        instructions = (
            "You generate an abstract logical relation label for a tree-structured graph chat interface. "
            "The user already decided the graph structure. Do not propose nodes, edges, or graph edits. "
            "Describe why the child branch exists relative to the parent branch, not what the child is about. "
            "Do not copy or summarize topic words, place names, entity names, or keywords from either node title. "
            f"Prefer one label from this set when it fits: {allowed_labels}. "
            f"When the child narrows the parent into a concrete subtopic, choose {specific_detail_label}. "
            f"When uncertain, choose {specific_detail_label}. "
            f"{bad_examples} "
            "Return exactly one short phrase. No quotes, no punctuation, no explanation. "
            f"Language: {language}. "
            "Length: Korean 1-3 eojeol, English 1-3 words."
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
            max_output_tokens=self._max_output_tokens,
        )
        return self._clean_phrase(phrase, fallback="구체화" if locale == "ko" else "Further detail")

    def _clean_phrase(self, text: str, fallback: str) -> str:
        line = (text or "").strip().splitlines()[0].strip()
        line = re.sub(r'^["“”\'`]+|["“”\'`]+$', "", line).strip()
        line = re.sub(r"[.!?。]+$", "", line).strip()
        return line[:60] or fallback
