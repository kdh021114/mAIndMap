from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List

from app.application.localization import (
    default_edge_phrase,
    default_graph_thread_title,
    default_node_title,
    default_root_title,
    pick_localized_text,
)
from app.domain.chat import ChatThread
from app.domain.common import create_id, utc_now_iso
from app.domain.graph import GraphEdge, GraphNode, GraphThread, NodePosition, TreeGraphPolicy
from app.domain.ports import (
    ChatRepository,
    EdgePhraseGenerator,
    GraphRepository,
    NodeTitleGenerator,
    SettingsRepository,
)


@dataclass(frozen=True)
class CreateNodeResult:
    node: GraphNode
    thread: ChatThread
    edge: GraphEdge | None = None


@dataclass(frozen=True)
class GraphThreadResult:
    graph_thread: GraphThread


class CreateGraphThreadUseCase:
    def __init__(self, graph_repository: GraphRepository, settings_repository: SettingsRepository):
        self._graph_repository = graph_repository
        self._settings_repository = settings_repository

    def execute(self, *, locale: str) -> GraphThreadResult:
        graph_thread_id = create_id("graph")
        index = len(self._graph_repository.list_graph_threads()) + 1
        graph_thread = GraphThread.new(
            graph_thread_id,
            {locale: default_graph_thread_title(locale, index)},
        )
        self._graph_repository.save_graph_thread(graph_thread)
        self._settings_repository.set_active_graph_thread_id(graph_thread.id)
        return GraphThreadResult(graph_thread=graph_thread)


class SwitchGraphThreadUseCase:
    def __init__(self, graph_repository: GraphRepository, settings_repository: SettingsRepository):
        self._graph_repository = graph_repository
        self._settings_repository = settings_repository

    def execute(self, *, graph_thread_id: str) -> GraphThread:
        graph_thread = self._graph_repository.get_graph_thread(graph_thread_id)
        self._settings_repository.set_active_graph_thread_id(graph_thread.id)
        return graph_thread


class DeleteGraphThreadUseCase:
    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        settings_repository: SettingsRepository,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._settings_repository = settings_repository

    def execute(self, *, graph_thread_id: str, locale: str) -> GraphThread:
        graph_thread = self._graph_repository.get_graph_thread(graph_thread_id)
        nodes_to_delete = self._graph_repository.list_nodes(graph_thread_id=graph_thread.id)
        self._graph_repository.delete_graph_thread(graph_thread.id)
        for node in nodes_to_delete:
            self._chat_repository.delete_thread_with_messages(node.thread_id)

        remaining = self._graph_repository.list_graph_threads()
        if not remaining:
            replacement = GraphThread.new(
                create_id("graph"),
                {locale: default_graph_thread_title(locale, 1)},
            )
            self._graph_repository.save_graph_thread(replacement)
            self._settings_repository.set_active_graph_thread_id(replacement.id)
            return replacement

        active_id = self._settings_repository.get_active_graph_thread_id()
        if graph_thread.id == active_id:
            self._settings_repository.set_active_graph_thread_id(remaining[0].id)
            return remaining[0]
        return self._graph_repository.get_graph_thread(active_id)


class CreateRootNodeUseCase:
    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        settings_repository: SettingsRepository,
        tree_policy: TreeGraphPolicy,
        root_position: NodePosition,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._settings_repository = settings_repository
        self._tree_policy = tree_policy
        self._root_position = root_position

    def execute(self, *, locale: str, position: NodePosition | None = None) -> CreateNodeResult:
        graph_thread_id = self._settings_repository.get_active_graph_thread_id()
        if self._graph_repository.list_nodes(graph_thread_id=graph_thread_id):
            raise ValueError("This prototype keeps one rooted tree. Add child nodes from the existing root.")

        node_id = create_id("node")
        thread_id = create_id("thread")
        title = {locale: default_root_title(locale)}
        node = GraphNode.new(
            node_id,
            graph_thread_id,
            thread_id,
            None,
            title,
            position or self._root_position,
            manually_positioned=position is not None,
        )
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
        default_horizontal_gap: int,
        default_vertical_gap: int,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._tree_policy = tree_policy
        self._default_horizontal_gap = default_horizontal_gap
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
            parent.graph_thread_id,
            thread_id,
            parent.id,
            child_title,
            position or self._next_child_position(parent),
            manually_positioned=position is not None,
        )
        thread = ChatThread.new(thread_id, node.id, child_title)
        edge = GraphEdge.new(
            create_id("edge"),
            graph_thread_id=parent.graph_thread_id,
            source_node_id=parent.id,
            target_node_id=node.id,
            phrase={locale: default_edge_phrase(locale)},
            phrase_generated_by="system",
        )

        candidate_nodes = [*self._graph_repository.list_nodes(graph_thread_id=parent.graph_thread_id), node]
        self._tree_policy.assert_valid_tree(candidate_nodes)

        rebalanced_nodes = []
        if position is None:
            rebalanced_nodes = self._rebalance_auto_children(
                parent=parent,
                candidate_nodes=candidate_nodes,
            )

        self._graph_repository.save_node(node)
        for sibling in rebalanced_nodes:
            self._graph_repository.save_node(sibling)
        self._graph_repository.save_edge(edge)
        self._chat_repository.save_thread(thread)
        return CreateNodeResult(node=node, thread=thread, edge=edge)

    def _next_child_position(self, parent: GraphNode) -> NodePosition:
        return NodePosition(
            x=parent.position.x,
            y=parent.position.y + self._default_vertical_gap,
        )

    def _rebalance_auto_children(
        self,
        *,
        parent: GraphNode,
        candidate_nodes: List[GraphNode],
    ) -> List[GraphNode]:
        auto_children = [
            node
            for node in candidate_nodes
            if node.parent_node_id == parent.id and not node.manually_positioned
        ]
        auto_children.sort(key=lambda node: node.created_at)
        if not auto_children:
            return []

        center_x = parent.position.x
        shared_y = parent.position.y + self._default_vertical_gap
        start_x = center_x - ((len(auto_children) - 1) * self._default_horizontal_gap) / 2
        return [
            node.with_position(
                NodePosition(
                    x=start_x + index * self._default_horizontal_gap,
                    y=shared_y,
                ),
                manually_positioned=False,
            )
            for index, node in enumerate(auto_children)
        ]


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


class MoveNodesUseCase:
    def __init__(self, graph_repository: GraphRepository):
        self._graph_repository = graph_repository

    def execute(self, *, positions: Dict[str, NodePosition]) -> List[GraphNode]:
        updated_nodes = []
        for node_id, position in positions.items():
            node = self._graph_repository.get_node(node_id)
            updated_nodes.append(self._graph_repository.save_node(node.with_position(position)))
        return updated_nodes


class DeleteNodeUseCase:
    def __init__(self, graph_repository: GraphRepository, chat_repository: ChatRepository):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository

    def execute(self, *, node_id: str) -> None:
        _delete_node_subtrees(
            graph_repository=self._graph_repository,
            chat_repository=self._chat_repository,
            node_ids=[node_id],
        )


class DeleteNodesUseCase:
    def __init__(self, graph_repository: GraphRepository, chat_repository: ChatRepository):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository

    def execute(self, *, node_ids: Iterable[str]) -> None:
        _delete_node_subtrees(
            graph_repository=self._graph_repository,
            chat_repository=self._chat_repository,
            node_ids=node_ids,
        )


def _delete_node_subtrees(
    *,
    graph_repository: GraphRepository,
    chat_repository: ChatRepository,
    node_ids: Iterable[str],
) -> None:
    unique_node_ids = list(dict.fromkeys(node_ids))
    if not unique_node_ids:
        return

    nodes = graph_repository.list_nodes()
    nodes_by_id = {node.id: node for node in nodes}
    selected_nodes = [graph_repository.get_node(node_id) for node_id in unique_node_ids]
    selected_node_ids = {node.id for node in selected_nodes}

    children: Dict[str, List[GraphNode]] = {}
    for node in nodes:
        if node.parent_node_id is not None:
            children.setdefault(node.parent_node_id, []).append(node)

    selected_roots = [
        node
        for node in selected_nodes
        if not _has_selected_ancestor(
            node=node,
            nodes_by_id=nodes_by_id,
            selected_node_ids=selected_node_ids,
        )
    ]

    thread_ids_to_delete: List[str] = []
    seen_thread_ids = set()
    for root in selected_roots:
        for node in _walk_subtree(root, children):
            if node.thread_id in seen_thread_ids:
                continue
            seen_thread_ids.add(node.thread_id)
            thread_ids_to_delete.append(node.thread_id)

    for root in selected_roots:
        graph_repository.delete_subtree(root.id)
    for thread_id in thread_ids_to_delete:
        chat_repository.delete_thread_with_messages(thread_id)


def _has_selected_ancestor(
    *,
    node: GraphNode,
    nodes_by_id: Dict[str, GraphNode],
    selected_node_ids: set[str],
) -> bool:
    parent_id = node.parent_node_id
    while parent_id is not None:
        if parent_id in selected_node_ids:
            return True
        parent = nodes_by_id.get(parent_id)
        parent_id = parent.parent_node_id if parent is not None else None
    return False


def _walk_subtree(root: GraphNode, children: Dict[str, List[GraphNode]]) -> List[GraphNode]:
    subtree: List[GraphNode] = []
    stack = [root]
    while stack:
        node = stack.pop()
        subtree.append(node)
        stack.extend(children.get(node.id, []))
    return subtree


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
