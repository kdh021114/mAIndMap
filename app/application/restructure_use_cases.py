from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, List

from app.application.localization import (
    default_edge_phrase,
    default_node_title,
    pick_localized_text,
)
from app.domain.chat import ChatThread
from app.domain.common import create_id, utc_now_iso
from app.domain.graph import (
    GraphEdge,
    GraphNode,
    NodePosition,
    TreeGraphPolicy,
)
from app.domain.ports import (
    ChatRepository,
    EdgePhraseGenerator,
    GraphRepository,
    NodeTitleGenerator,
)


@dataclass(frozen=True)
class MergeNodesResult:
    surviving_node: GraphNode


@dataclass(frozen=True)
class SplitNodeResult:
    source_node: GraphNode
    new_node: GraphNode
    new_edge: GraphEdge


class MergeSiblingNodesUseCase:
    """Merge two or more sibling nodes into the first one (the absorber).

    Constraints:
    - All selected nodes must share the same parent node (sibling-only merge).
    - The first node id in the input list becomes the absorber. The rest are
      absorbed: their messages are reassigned to the absorber's thread and any
      children are re-parented to the absorber. The absorbed nodes, their incoming
      edges, and their now-empty threads are deleted.
    """

    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        tree_policy: TreeGraphPolicy,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._tree_policy = tree_policy

    def execute(self, *, node_ids: Iterable[str]) -> MergeNodesResult:
        ordered_ids = list(dict.fromkeys(node_ids))
        if len(ordered_ids) < 2:
            raise ValueError("Merging requires at least two nodes.")

        nodes = [self._graph_repository.get_node(node_id) for node_id in ordered_ids]
        parent_ids = {node.parent_node_id for node in nodes}
        if len(parent_ids) != 1 or next(iter(parent_ids)) is None:
            raise ValueError("Only sibling nodes that share a parent can be merged.")
        graph_thread_ids = {node.graph_thread_id for node in nodes}
        if len(graph_thread_ids) != 1:
            raise ValueError("Nodes must belong to the same graph thread.")

        absorber = nodes[0]
        absorbed = nodes[1:]
        absorbed_ids = {node.id for node in absorbed}

        all_nodes = self._graph_repository.list_nodes(graph_thread_id=absorber.graph_thread_id)
        all_edges = self._graph_repository.list_edges(graph_thread_id=absorber.graph_thread_id)

        for absorbed_node in absorbed:
            messages = self._chat_repository.list_messages(absorbed_node.thread_id)
            if messages:
                self._chat_repository.reassign_messages_to_thread(
                    [message.id for message in messages],
                    absorber.thread_id,
                )

        for edge in all_edges:
            if edge.source_node_id in absorbed_ids:
                updated_edge = replace(
                    edge,
                    source_node_id=absorber.id,
                    updated_at=utc_now_iso(),
                )
                self._graph_repository.save_edge(updated_edge)

        for node in all_nodes:
            if node.parent_node_id in absorbed_ids:
                reparented = replace(
                    node,
                    parent_node_id=absorber.id,
                    updated_at=utc_now_iso(),
                )
                self._graph_repository.save_node(reparented)

        for absorbed_node in absorbed:
            incoming_edge = self._graph_repository.get_edge_by_target(absorbed_node.id)
            if incoming_edge is not None:
                self._graph_repository.delete_edge(incoming_edge.id)
            # At this point all children have been re-parented to the absorber,
            # so the absorbed node is guaranteed to be a leaf; delete_subtree
            # is a safe leaf delete.
            self._graph_repository.delete_subtree(absorbed_node.id)
            self._chat_repository.delete_thread_with_messages(absorbed_node.thread_id)

        updated_absorber = self._graph_repository.get_node(absorber.id)
        absorber_thread = self._chat_repository.get_thread(absorber.thread_id)
        self._chat_repository.save_thread(
            ChatThread(
                id=absorber_thread.id,
                title=absorber_thread.title,
                node_id=absorber_thread.node_id,
                created_at=absorber_thread.created_at,
                updated_at=utc_now_iso(),
            )
        )

        remaining = self._graph_repository.list_nodes(graph_thread_id=absorber.graph_thread_id)
        self._tree_policy.assert_valid_tree(remaining)
        return MergeNodesResult(surviving_node=updated_absorber)

class SplitNodeUseCase:
    """Split selected messages out of a node into a new child node.

    The selected message ids must all belong to the source node's thread. A new
    child node is created under the source node, the selected messages are
    reassigned to the new node's thread, and a default-labelled edge is created
    from source -> new node. Title generation for the new node happens lazily
    on the next prompt or locale change, just like ordinary child nodes.
    """

    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        tree_policy: TreeGraphPolicy,
        title_generator: NodeTitleGenerator,
        edge_phrase_generator: EdgePhraseGenerator,
        default_vertical_gap: int,
        default_horizontal_gap: int,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._tree_policy = tree_policy
        self._title_generator = title_generator
        self._edge_phrase_generator = edge_phrase_generator
        self._default_vertical_gap = default_vertical_gap
        self._default_horizontal_gap = default_horizontal_gap

    def execute(self, *, source_node_id: str, message_ids: Iterable[str], locale: str) -> SplitNodeResult:
        ordered_message_ids = list(dict.fromkeys(message_ids))
        if not ordered_message_ids:
            raise ValueError("Splitting requires at least one message.")

        source = self._graph_repository.get_node(source_node_id)
        source_messages = self._chat_repository.list_messages(source.thread_id)
        source_message_ids = {message.id for message in source_messages}

        invalid = [mid for mid in ordered_message_ids if mid not in source_message_ids]
        if invalid:
            raise ValueError(f"These messages do not belong to the source node: {invalid}")
        if len(ordered_message_ids) == len(source_messages):
            raise ValueError("Cannot split out every message from a node.")

        moved_messages = [m for m in source_messages if m.id in set(ordered_message_ids)]
        first_user_in_moved = next((m for m in moved_messages if m.role == "user"), None)

        new_node_id = create_id("node")
        new_thread_id = create_id("thread")
        new_node_title = (
            self._title_generator.generate(
                first_user_prompt=first_user_in_moved.content,
                locale=locale,
            )
            if first_user_in_moved is not None
            else default_node_title(locale)
        )
        title_map = {locale: new_node_title}

        new_node = GraphNode.new(
            new_node_id,
            graph_thread_id=source.graph_thread_id,
            thread_id=new_thread_id,
            parent_node_id=source.id,
            title=title_map,
            position=NodePosition(
                x=source.position.x + self._default_horizontal_gap,
                y=source.position.y + self._default_vertical_gap,
            ),
            manually_positioned=False,
        )
        thread = ChatThread.new(new_thread_id, new_node.id, title_map)

        edge_phrase = (
            self._edge_phrase_generator.generate(
                source_title=pick_localized_text(source.title, locale, fallback="Parent"),
                target_title=new_node_title,
                first_user_prompt=first_user_in_moved.content if first_user_in_moved else "",
                locale=locale,
            )
            if first_user_in_moved is not None
            else default_edge_phrase(locale)
        )
        edge = GraphEdge.new(
            create_id("edge"),
            graph_thread_id=source.graph_thread_id,
            source_node_id=source.id,
            target_node_id=new_node.id,
            phrase={locale: edge_phrase},
            phrase_generated_by="ai" if first_user_in_moved is not None else "system",
        )

        candidate_nodes = [
            *self._graph_repository.list_nodes(graph_thread_id=source.graph_thread_id),
            new_node,
        ]
        self._tree_policy.assert_valid_tree(candidate_nodes)

        self._graph_repository.save_node(new_node)
        self._graph_repository.save_edge(edge)
        self._chat_repository.save_thread(thread)
        self._chat_repository.reassign_messages_to_thread(ordered_message_ids, new_thread_id)

        return SplitNodeResult(source_node=source, new_node=new_node, new_edge=edge)


