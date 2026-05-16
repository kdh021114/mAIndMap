from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.application.context_builder import AncestorLineageContextBuilder
from app.application.localization import pick_localized_text
from app.domain.chat import ChatThread, Message
from app.domain.common import create_id, utc_now_iso
from app.domain.graph import GraphEdge, GraphNode
from app.domain.ports import (
    ChatModel,
    ChatRepository,
    EdgePhraseGenerator,
    GraphRepository,
    NodeTitleGenerator,
)


@dataclass(frozen=True)
class SendMessageResult:
    user_message: Message
    assistant_message: Message
    updated_node: GraphNode | None
    updated_edge: GraphEdge | None


class LoadThreadMessagesUseCase:
    def __init__(self, chat_repository: ChatRepository):
        self._chat_repository = chat_repository

    def execute(self, *, thread_id: str) -> List[Message]:
        return self._chat_repository.list_messages(thread_id)


class SendMessageUseCase:
    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        chat_model: ChatModel,
        title_generator: NodeTitleGenerator,
        edge_phrase_generator: EdgePhraseGenerator,
        ancestor_context_builder: AncestorLineageContextBuilder,
        current_thread_message_limit: int,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._chat_model = chat_model
        self._title_generator = title_generator
        self._edge_phrase_generator = edge_phrase_generator
        self._ancestor_context_builder = ancestor_context_builder
        self._current_thread_message_limit = current_thread_message_limit

    def execute(self, *, node_id: str, content: str, locale: str) -> SendMessageResult:
        if not content.strip():
            raise ValueError("Message is empty.")

        node = self._graph_repository.get_node(node_id)
        user_message = Message.new(
            message_id=create_id("msg"),
            thread_id=node.thread_id,
            role="user",
            content=content.strip(),
        )
        self._chat_repository.add_message(user_message)

        system_prompt = self._build_system_prompt(node_id=node.id, locale=locale)
        current_messages = self._chat_repository.list_messages(node.thread_id)[
            -self._current_thread_message_limit :
        ]
        assistant_text = self._chat_model.generate_reply(
            system_prompt=system_prompt,
            messages=current_messages,
        )
        assistant_message = Message.new(
            message_id=create_id("msg"),
            thread_id=node.thread_id,
            role="assistant",
            content=assistant_text,
        )
        self._chat_repository.add_message(assistant_message)

        updated_node = None
        updated_edge = None
        if self._chat_repository.count_user_messages(node.thread_id) == 1:
            updated_node = self._generate_first_prompt_title(
                node=node,
                first_user_prompt=user_message.content,
                locale=locale,
            )
            updated_edge = self._generate_first_prompt_edge_phrase(
                node=updated_node,
                first_user_prompt=user_message.content,
                locale=locale,
            )

        return SendMessageResult(
            user_message=user_message,
            assistant_message=assistant_message,
            updated_node=updated_node,
            updated_edge=updated_edge,
        )

    def _build_system_prompt(self, *, node_id: str, locale: str) -> str:
        ancestor_context = self._ancestor_context_builder.build(node_id=node_id, locale=locale)
        language_hint = "Korean" if locale == "ko" else "English"
        base = (
            "You are the assistant inside a tree-structured graph chat prototype. "
            "The user manually creates graph nodes. Do not suggest creating graph nodes or graph edges unless explicitly asked. "
            "Use the selected node's current conversation as the main conversation. "
            "Use the provided root-to-parent ancestor lineage only as background; do not bring in sibling or child-node context. "
            f"Respond primarily in {language_hint}, unless the user clearly requests another language."
        )
        if ancestor_context:
            return base + "\n\nRoot-to-parent ancestor lineage available to you:\n" + ancestor_context
        return base + "\n\nThis is a root node or no ancestor context is available."

    def _generate_first_prompt_title(self, *, node: GraphNode, first_user_prompt: str, locale: str) -> GraphNode:
        if node.user_edited_title_locales.get(locale):
            return node
        title = self._title_generator.generate(first_user_prompt=first_user_prompt, locale=locale)
        updated_node = node.with_title(locale=locale, title=title, edited_by_user=False)
        self._graph_repository.save_node(updated_node)

        thread = self._chat_repository.get_thread(node.thread_id)
        titles = dict(thread.title)
        titles[locale] = title
        self._chat_repository.save_thread(
            ChatThread(
                id=thread.id,
                title=titles,
                node_id=thread.node_id,
                created_at=thread.created_at,
                updated_at=utc_now_iso(),
            )
        )
        return updated_node

    def _generate_first_prompt_edge_phrase(
        self,
        *,
        node: GraphNode,
        first_user_prompt: str,
        locale: str,
    ) -> GraphEdge | None:
        edge = self._graph_repository.get_edge_by_target(node.id)
        if edge is None:
            return None
        if edge.user_edited_phrase_locales.get(locale):
            return edge

        parent = self._graph_repository.get_node(edge.source_node_id)
        phrase = self._edge_phrase_generator.generate(
            source_title=pick_localized_text(parent.title, locale, fallback="Parent"),
            target_title=pick_localized_text(node.title, locale, fallback="Child"),
            first_user_prompt=first_user_prompt,
            locale=locale,
        )
        updated_edge = edge.with_phrase(
            locale=locale,
            phrase=phrase,
            generated_by="ai",
            edited_by_user=False,
        )
        self._graph_repository.save_edge(updated_edge)
        return updated_edge
