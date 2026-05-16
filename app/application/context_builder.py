from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.application.localization import pick_localized_text
from app.domain.chat import Message
from app.domain.graph import GraphEdge, GraphNode
from app.domain.ports import ChatRepository, GraphRepository


@dataclass(frozen=True)
class AncestorContextPolicy:
    """Controls which ancestor context is exposed to the chat model.

    The intended experimental condition is a tree path policy: for the selected
    node, pass the single root-to-parent lineage and never pass siblings or child
    branches. This operationalizes "parent context" as the whole parent path,
    not only the direct parent.
    """

    include_full_ancestor_lineage: bool
    message_limit_per_ancestor: int


class AncestorLineageContextBuilder:
    """Builds LLM context from the selected node's root-to-parent lineage.

    For a selected node C in Root -> A -> B -> C, this builder includes Root,
    A, and B. It does not include sibling branches or descendants of C. The
    selected node's own messages are supplied separately by SendMessageUseCase.
    """

    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        policy: AncestorContextPolicy,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._policy = policy

    def build(self, *, node_id: str, locale: str) -> str:
        if not self._policy.include_full_ancestor_lineage:
            return ""

        selected_node = self._graph_repository.get_node(node_id)
        ancestors = self._get_ancestors_root_to_parent(selected_node)
        if not ancestors:
            return ""

        blocks: List[str] = [
            "Ancestor lineage visible to the model: root -> ... -> direct parent.",
            "Only this single path is included; sibling and child branches are intentionally excluded.",
            "",
        ]

        for index, ancestor in enumerate(ancestors, start=1):
            title = pick_localized_text(ancestor.title, locale, fallback="Untitled")
            incoming_edge = self._incoming_edge_for_lineage_node(
                lineage_nodes=[*ancestors, selected_node],
                target_node=ancestor,
            )
            relation_line = self._format_incoming_relation(incoming_edge, locale)
            messages = self._chat_repository.list_messages(ancestor.thread_id)[
                -self._policy.message_limit_per_ancestor :
            ]
            message_lines = self._format_messages(messages)
            blocks.append(
                f"Lineage node {index}/{len(ancestors)}: {title}\n"
                f"{relation_line}\n"
                f"Recent conversation in this ancestor node:\n{message_lines or '(no messages yet)'}"
            )

        selected_title = pick_localized_text(selected_node.title, locale, fallback="Selected node")
        selected_incoming_edge = self._find_edge(
            source_node_id=ancestors[-1].id,
            target_node_id=selected_node.id,
        )
        blocks.append(
            "Selected current node, whose messages are provided separately:\n"
            f"Title: {selected_title}\n"
            f"{self._format_incoming_relation(selected_incoming_edge, locale)}"
        )
        return "\n\n".join(blocks)

    def _get_ancestors_root_to_parent(self, node: GraphNode) -> List[GraphNode]:
        ancestors_parent_to_root: List[GraphNode] = []
        parent_id: Optional[str] = node.parent_node_id
        seen: set[str] = set()

        while parent_id:
            if parent_id in seen:
                raise ValueError("Tree cycle detected while building ancestor context.")
            seen.add(parent_id)
            parent = self._graph_repository.get_node(parent_id)
            ancestors_parent_to_root.append(parent)
            parent_id = parent.parent_node_id

        return list(reversed(ancestors_parent_to_root))

    def _incoming_edge_for_lineage_node(
        self,
        *,
        lineage_nodes: List[GraphNode],
        target_node: GraphNode,
    ) -> Optional[GraphEdge]:
        try:
            target_index = next(index for index, node in enumerate(lineage_nodes) if node.id == target_node.id)
        except StopIteration:
            return None
        if target_index == 0:
            return None
        source = lineage_nodes[target_index - 1]
        return self._find_edge(source_node_id=source.id, target_node_id=target_node.id)

    def _find_edge(self, *, source_node_id: str, target_node_id: str) -> Optional[GraphEdge]:
        for edge in self._graph_repository.list_edges():
            if edge.source_node_id == source_node_id and edge.target_node_id == target_node_id:
                return edge
        return None

    def _format_incoming_relation(self, edge: Optional[GraphEdge], locale: str) -> str:
        if edge is None:
            return "Incoming relation from previous path node: (root node)"
        phrase = pick_localized_text(edge.phrase, locale, fallback="unlabeled relation")
        return f"Incoming relation from previous path node: {phrase}"

    def _format_messages(self, messages: List[Message]) -> str:
        return "\n".join(f"- {m.role}: {m.content}" for m in messages)


# Backward-compatible names. They let older imports keep working while the
# implementation now correctly uses the full root-to-parent lineage.
ParentContextPolicy = AncestorContextPolicy
ParentContextBuilder = AncestorLineageContextBuilder
