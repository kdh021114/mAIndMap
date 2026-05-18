from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, Optional

from app.domain.common import LocalizedText, utc_now_iso


DEFAULT_GRAPH_THREAD_ID = "graph_default"


@dataclass(frozen=True)
class GraphThread:
    """A top-level workspace thread that owns one independent graph."""

    id: str
    title: LocalizedText
    created_at: str
    updated_at: str

    @staticmethod
    def new(graph_thread_id: str, title: LocalizedText) -> "GraphThread":
        now = utc_now_iso()
        return GraphThread(
            id=graph_thread_id,
            title=title,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def from_dict(data: dict) -> "GraphThread":
        return GraphThread(
            id=data["id"],
            title=dict(data.get("title", {})),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def with_title(self, locale: str, title: str) -> "GraphThread":
        titles = dict(self.title)
        titles[locale] = title.strip()
        return replace(self, title=titles, updated_at=utc_now_iso())


@dataclass(frozen=True)
class NodePosition:
    """Canvas-space top-left coordinate for a graph node."""

    x: float
    y: float

    @staticmethod
    def from_dict(data: dict | None) -> "NodePosition":
        if not data:
            return NodePosition(x=0, y=0)
        return NodePosition(x=float(data.get("x", 0)), y=float(data.get("y", 0)))


@dataclass(frozen=True)
class GraphNode:
    """A tree node representing one chat thread.

    The title shown in the graph is a localized short LLM-generated conversation
    title/summary, similar to automatic chat-thread titles.
    """

    id: str
    graph_thread_id: str
    thread_id: str
    parent_node_id: Optional[str]
    title: LocalizedText
    user_edited_title_locales: Dict[str, bool]
    position: NodePosition
    manually_positioned: bool
    created_at: str
    updated_at: str

    @staticmethod
    def new(
        node_id: str,
        graph_thread_id: str,
        thread_id: str,
        parent_node_id: Optional[str],
        title: LocalizedText,
        position: NodePosition | None = None,
        manually_positioned: bool = False,
    ) -> "GraphNode":
        now = utc_now_iso()
        return GraphNode(
            id=node_id,
            graph_thread_id=graph_thread_id,
            thread_id=thread_id,
            parent_node_id=parent_node_id,
            title=title,
            user_edited_title_locales={},
            position=position or NodePosition(x=0, y=0),
            manually_positioned=manually_positioned,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def from_dict(data: dict) -> "GraphNode":
        return GraphNode(
            id=data["id"],
            graph_thread_id=data.get("graph_thread_id", DEFAULT_GRAPH_THREAD_ID),
            thread_id=data["thread_id"],
            parent_node_id=data.get("parent_node_id"),
            title=dict(data.get("title", {})),
            user_edited_title_locales=dict(data.get("user_edited_title_locales", {})),
            position=NodePosition.from_dict(data.get("position")),
            manually_positioned=bool(data.get("manually_positioned", False)),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def with_title(self, locale: str, title: str, edited_by_user: bool) -> "GraphNode":
        titles = dict(self.title)
        titles[locale] = title.strip()
        edited = dict(self.user_edited_title_locales)
        edited[locale] = edited_by_user
        return replace(
            self,
            title=titles,
            user_edited_title_locales=edited,
            updated_at=utc_now_iso(),
        )

    def with_position(self, position: NodePosition, *, manually_positioned: bool = True) -> "GraphNode":
        return replace(
            self,
            position=position,
            manually_positioned=manually_positioned,
            updated_at=utc_now_iso(),
        )


@dataclass(frozen=True)
class GraphEdge:
    """A parent-child tree edge with a phrase-level relation label."""

    id: str
    graph_thread_id: str
    source_node_id: str
    target_node_id: str
    phrase: LocalizedText
    phrase_generated_by: str
    user_edited_phrase_locales: Dict[str, bool]
    created_at: str
    updated_at: str

    @staticmethod
    def new(
        edge_id: str,
        graph_thread_id: str,
        source_node_id: str,
        target_node_id: str,
        phrase: LocalizedText,
        phrase_generated_by: str = "system",
    ) -> "GraphEdge":
        now = utc_now_iso()
        return GraphEdge(
            id=edge_id,
            graph_thread_id=graph_thread_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            phrase=phrase,
            phrase_generated_by=phrase_generated_by,
            user_edited_phrase_locales={},
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def from_dict(data: dict) -> "GraphEdge":
        return GraphEdge(
            id=data["id"],
            graph_thread_id=data.get("graph_thread_id", DEFAULT_GRAPH_THREAD_ID),
            source_node_id=data["source_node_id"],
            target_node_id=data["target_node_id"],
            phrase=dict(data.get("phrase", {})),
            phrase_generated_by=data.get("phrase_generated_by", "system"),
            user_edited_phrase_locales=dict(data.get("user_edited_phrase_locales", {})),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )

    def with_phrase(self, locale: str, phrase: str, generated_by: str, edited_by_user: bool) -> "GraphEdge":
        phrases = dict(self.phrase)
        phrases[locale] = phrase.strip()
        edited = dict(self.user_edited_phrase_locales)
        edited[locale] = edited_by_user
        return replace(
            self,
            phrase=phrases,
            phrase_generated_by=generated_by,
            user_edited_phrase_locales=edited,
            updated_at=utc_now_iso(),
        )


class TreeGraphPolicy:
    """Domain policy enforcing that the visual structure remains a tree."""

    def assert_can_add_child(self, parent_node: GraphNode) -> None:
        if parent_node is None:
            raise ValueError("Parent node does not exist.")

    def assert_valid_tree(self, nodes: Iterable[GraphNode]) -> None:
        node_list = list(nodes)
        ids = {n.id for n in node_list}
        roots = [n for n in node_list if n.parent_node_id is None]
        if len(roots) > 1:
            raise ValueError("Tree must have at most one root in this prototype.")
        for node in node_list:
            if node.parent_node_id is not None and node.parent_node_id not in ids:
                raise ValueError(f"Node {node.id} has a missing parent {node.parent_node_id}.")
        self._assert_acyclic(node_list)

    def _assert_acyclic(self, nodes: List[GraphNode]) -> None:
        by_id = {n.id: n for n in nodes}
        for node in nodes:
            seen = set()
            cursor = node
            while cursor.parent_node_id is not None:
                if cursor.id in seen:
                    raise ValueError("Tree cycle detected.")
                seen.add(cursor.id)
                cursor = by_id[cursor.parent_node_id]
