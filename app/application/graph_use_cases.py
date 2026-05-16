from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from app.application.localization import (
    default_edge_phrase,
    default_node_title,
    default_root_title,
    pick_localized_text,
)
from app.domain.chat import ChatThread
from app.domain.common import create_id, utc_now_iso
from app.domain.graph import GraphEdge, GraphNode, NodePosition, TreeGraphPolicy
from app.domain.ports import ChatRepository, EdgePhraseGenerator, GraphRepository, NodeTitleGenerator


@dataclass(frozen=True)
class CreateNodeResult:
    node: GraphNode
    thread: ChatThread
    edge: GraphEdge | None = None


class CreateRootNodeUseCase:
    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        tree_policy: TreeGraphPolicy,
        root_position: NodePosition,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._tree_policy = tree_policy
        self._root_position = root_position

    def execute(self, *, locale: str, position: NodePosition | None = None) -> CreateNodeResult:
        if self._graph_repository.list_nodes():
            raise ValueError("This prototype keeps one rooted tree. Add child nodes from the existing root.")

        node_id = create_id("node")
        thread_id = create_id("thread")
        title = {locale: default_root_title(locale)}
        node = GraphNode.new(node_id, thread_id, None, title, position or self._root_position)
        thread = ChatThread.new(thread_id, node_id, title)

        self._tree_policy.assert_valid_tree([node])
        self._graph_repository.save_node(node)
        self._chat_repository.save_thread(thread)
        return CreateNodeResult(node=node, thread=thread)


class AddChildNodeUseCase:
    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        tree_policy: TreeGraphPolicy,
        default_vertical_gap: int,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._tree_policy = tree_policy
        self._default_vertical_gap = default_vertical_gap

    def execute(
        self,
        *,
        parent_node_id: str,
        locale: str,
        position: NodePosition | None = None,
    ) -> CreateNodeResult:
        parent = self._graph_repository.get_node(parent_node_id)
        self._tree_policy.assert_can_add_child(parent)

        node_id = create_id("node")
        thread_id = create_id("thread")
        child_title = {locale: default_node_title(locale)}
        node = GraphNode.new(
            node_id,
            thread_id,
            parent.id,
            child_title,
            position or self._next_child_position(parent),
        )
        thread = ChatThread.new(thread_id, node.id, child_title)
        edge = GraphEdge.new(
            create_id("edge"),
            source_node_id=parent.id,
            target_node_id=node.id,
            phrase={locale: default_edge_phrase(locale)},
            phrase_generated_by="system",
        )

        candidate_nodes = [*self._graph_repository.list_nodes(), node]
        self._tree_policy.assert_valid_tree(candidate_nodes)

        self._graph_repository.save_node(node)
        self._graph_repository.save_edge(edge)
        self._chat_repository.save_thread(thread)
        return CreateNodeResult(node=node, thread=thread, edge=edge)

    def _next_child_position(self, parent: GraphNode) -> NodePosition:
        siblings = [
            node
            for node in self._graph_repository.list_nodes()
            if node.parent_node_id == parent.id
        ]
        if not siblings:
            return NodePosition(
                x=parent.position.x,
                y=parent.position.y + self._default_vertical_gap,
            )

        lowest_sibling_y = max(node.position.y for node in siblings)
        return NodePosition(
            x=parent.position.x,
            y=lowest_sibling_y + self._default_vertical_gap,
        )


class EditEdgePhraseUseCase:
    def __init__(self, graph_repository: GraphRepository):
        self._graph_repository = graph_repository

    def execute(self, *, edge_id: str, locale: str, phrase: str) -> GraphEdge:
        edge = self._graph_repository.get_edge(edge_id)
        updated = edge.with_phrase(
            locale=locale,
            phrase=phrase,
            generated_by="user",
            edited_by_user=True,
        )
        return self._graph_repository.save_edge(updated)


class RenameNodeUseCase:
    def __init__(self, graph_repository: GraphRepository, chat_repository: ChatRepository):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository

    def execute(self, *, node_id: str, locale: str, title: str) -> GraphNode:
        node = self._graph_repository.get_node(node_id)
        updated_node = node.with_title(locale=locale, title=title, edited_by_user=True)
        self._graph_repository.save_node(updated_node)

        thread = self._chat_repository.get_thread(node.thread_id)
        updated_titles = dict(thread.title)
        updated_titles[locale] = title.strip()
        updated_thread = ChatThread(
            id=thread.id,
            title=updated_titles,
            node_id=thread.node_id,
            created_at=thread.created_at,
            updated_at=utc_now_iso(),
        )
        self._chat_repository.save_thread(updated_thread)
        return updated_node


class MoveNodeUseCase:
    def __init__(self, graph_repository: GraphRepository):
        self._graph_repository = graph_repository

    def execute(self, *, node_id: str, position: NodePosition) -> GraphNode:
        node = self._graph_repository.get_node(node_id)
        updated_node = node.with_position(position)
        return self._graph_repository.save_node(updated_node)


class DeleteNodeUseCase:
    def __init__(self, graph_repository: GraphRepository, chat_repository: ChatRepository):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository

    def execute(self, *, node_id: str) -> None:
        nodes = self._graph_repository.list_nodes()
        children: Dict[str, List[GraphNode]] = {}
        for node in nodes:
            if node.parent_node_id is not None:
                children.setdefault(node.parent_node_id, []).append(node)

        subtree: List[GraphNode] = []
        stack = [self._graph_repository.get_node(node_id)]
        while stack:
            node = stack.pop()
            subtree.append(node)
            stack.extend(children.get(node.id, []))

        self._graph_repository.delete_subtree(node_id)
        for node in subtree:
            self._chat_repository.delete_thread_with_messages(node.thread_id)


class GenerateMissingGraphLabelsUseCase:
    """Generates missing locale-specific node titles and edge phrases.

    This is called when the UI language changes. It never overwrites labels that
    the user has manually edited in that locale.
    """

    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        title_generator: NodeTitleGenerator,
        edge_phrase_generator: EdgePhraseGenerator,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._title_generator = title_generator
        self._edge_phrase_generator = edge_phrase_generator

    def execute(self, *, locale: str) -> None:
        self._generate_missing_titles(locale=locale)
        self._generate_missing_edge_phrases(locale=locale)

    def _generate_missing_titles(self, *, locale: str) -> None:
        for node in self._graph_repository.list_nodes():
            if node.title.get(locale) or node.user_edited_title_locales.get(locale):
                continue
            messages = self._chat_repository.list_messages(node.thread_id)
            first_user = next((m for m in messages if m.role == "user"), None)
            if first_user is None:
                continue
            title = self._title_generator.generate(
                first_user_prompt=first_user.content,
                locale=locale,
            )
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

    def _generate_missing_edge_phrases(self, *, locale: str) -> None:
        for edge in self._graph_repository.list_edges():
            if edge.phrase.get(locale) or edge.user_edited_phrase_locales.get(locale):
                continue
            source = self._graph_repository.get_node(edge.source_node_id)
            target = self._graph_repository.get_node(edge.target_node_id)
            target_messages = self._chat_repository.list_messages(target.thread_id)
            first_user = next((m for m in target_messages if m.role == "user"), None)
            phrase = self._edge_phrase_generator.generate(
                source_title=pick_localized_text(source.title, locale, fallback="Parent"),
                target_title=pick_localized_text(target.title, locale, fallback="Child"),
                first_user_prompt=first_user.content if first_user else "",
                locale=locale,
            )
            updated = edge.with_phrase(
                locale=locale,
                phrase=phrase,
                generated_by="ai",
                edited_by_user=False,
            )
            self._graph_repository.save_edge(updated)
