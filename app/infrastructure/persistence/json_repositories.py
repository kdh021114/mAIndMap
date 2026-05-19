from __future__ import annotations

from dataclasses import asdict, replace
from typing import List, Optional

from app.domain.chat import ChatThread, Message
from app.domain.common import utc_now_iso
from app.domain.graph import GraphEdge, GraphNode, GraphThread
from app.domain.ports import (
    ChatRepository,
    GraphRepository,
    SettingsRepository,
    WorkspaceSnapshotRepository,
)
from app.infrastructure.persistence.json_store import JsonStore


class JsonGraphRepository(GraphRepository):
    def __init__(self, store: JsonStore):
        self._store = store

    def list_graph_threads(self) -> List[GraphThread]:
        state = self._store.read()
        graph_threads = [GraphThread.from_dict(v) for v in state["graph_threads"].values()]
        return sorted(graph_threads, key=lambda graph_thread: graph_thread.created_at)

    def get_graph_thread(self, graph_thread_id: str) -> GraphThread:
        state = self._store.read()
        try:
            return GraphThread.from_dict(state["graph_threads"][graph_thread_id])
        except KeyError as exc:
            raise KeyError(f"Graph thread not found: {graph_thread_id}") from exc

    def save_graph_thread(self, graph_thread: GraphThread) -> GraphThread:
        def mutate(state: dict) -> None:
            state["graph_threads"][graph_thread.id] = asdict(graph_thread)

        self._store.update(mutate)
        return graph_thread

    def delete_graph_thread(self, graph_thread_id: str) -> None:
        def mutate(state: dict) -> None:
            state["graph_threads"].pop(graph_thread_id, None)
            node_ids = [
                node_id
                for node_id, node in state["nodes"].items()
                if node.get("graph_thread_id") == graph_thread_id
            ]
            for node_id in node_ids:
                state["nodes"].pop(node_id, None)
            edge_ids = [
                edge_id
                for edge_id, edge in state["edges"].items()
                if edge.get("graph_thread_id") == graph_thread_id
            ]
            for edge_id in edge_ids:
                state["edges"].pop(edge_id, None)

        self._store.update(mutate)

    def list_nodes(self, graph_thread_id: str | None = None) -> List[GraphNode]:
        state = self._store.read()
        nodes = [GraphNode.from_dict(v) for v in state["nodes"].values()]
        if graph_thread_id is not None:
            nodes = [node for node in nodes if node.graph_thread_id == graph_thread_id]
        return nodes

    def list_edges(self, graph_thread_id: str | None = None) -> List[GraphEdge]:
        state = self._store.read()
        edges = [GraphEdge.from_dict(v) for v in state["edges"].values()]
        if graph_thread_id is not None:
            edges = [edge for edge in edges if edge.graph_thread_id == graph_thread_id]
        return edges

    def get_node(self, node_id: str) -> GraphNode:
        state = self._store.read()
        try:
            return GraphNode.from_dict(state["nodes"][node_id])
        except KeyError as exc:
            raise KeyError(f"Node not found: {node_id}") from exc

    def get_node_by_thread(self, thread_id: str) -> GraphNode:
        for node in self.list_nodes():
            if node.thread_id == thread_id:
                return node
        raise KeyError(f"Node not found for thread: {thread_id}")

    def get_edge_by_target(self, target_node_id: str) -> Optional[GraphEdge]:
        for edge in self.list_edges():
            if edge.target_node_id == target_node_id:
                return edge
        return None

    def get_edge(self, edge_id: str) -> GraphEdge:
        state = self._store.read()
        try:
            return GraphEdge.from_dict(state["edges"][edge_id])
        except KeyError as exc:
            raise KeyError(f"Edge not found: {edge_id}") from exc

    def save_node(self, node: GraphNode) -> GraphNode:
        def mutate(state: dict) -> None:
            state["nodes"][node.id] = asdict(node)

        self._store.update(mutate)
        return node

    def save_edge(self, edge: GraphEdge) -> GraphEdge:
        def mutate(state: dict) -> None:
            state["edges"][edge.id] = asdict(edge)

        self._store.update(mutate)
        return edge

    def delete_edge(self, edge_id: str) -> None:
        def mutate(state: dict) -> None:
            state["edges"].pop(edge_id, None)

        self._store.update(mutate)

    def delete_subtree(self, root_node_id: str) -> None:
        nodes = self.list_nodes()
        children_by_parent = {}
        for node in nodes:
            children_by_parent.setdefault(node.parent_node_id, []).append(node.id)

        to_delete = []
        stack = [root_node_id]
        while stack:
            node_id = stack.pop()
            to_delete.append(node_id)
            stack.extend(children_by_parent.get(node_id, []))

        def mutate(state: dict) -> None:
            for node_id in to_delete:
                state["nodes"].pop(node_id, None)
            edge_ids = [
                edge_id
                for edge_id, edge in state["edges"].items()
                if edge["source_node_id"] in to_delete or edge["target_node_id"] in to_delete
            ]
            for edge_id in edge_ids:
                state["edges"].pop(edge_id, None)

        self._store.update(mutate)


class JsonChatRepository(ChatRepository):
    def __init__(self, store: JsonStore):
        self._store = store

    def list_threads(self) -> List[ChatThread]:
        state = self._store.read()
        return [ChatThread.from_dict(v) for v in state["threads"].values()]

    def get_thread(self, thread_id: str) -> ChatThread:
        state = self._store.read()
        try:
            return ChatThread.from_dict(state["threads"][thread_id])
        except KeyError as exc:
            raise KeyError(f"Thread not found: {thread_id}") from exc

    def save_thread(self, thread: ChatThread) -> ChatThread:
        def mutate(state: dict) -> None:
            state["threads"][thread.id] = asdict(thread)

        self._store.update(mutate)
        return thread

    def add_message(self, message: Message) -> Message:
        def mutate(state: dict) -> None:
            state["messages"][message.id] = asdict(message)
            if message.thread_id in state["threads"]:
                state["threads"][message.thread_id]["updated_at"] = utc_now_iso()

        self._store.update(mutate)
        return message

    def list_messages(self, thread_id: str) -> List[Message]:
        state = self._store.read()
        messages = [
            Message.from_dict(v)
            for v in state["messages"].values()
            if v["thread_id"] == thread_id
        ]
        return sorted(messages, key=lambda m: m.created_at)

    def count_user_messages(self, thread_id: str) -> int:
        return sum(1 for m in self.list_messages(thread_id) if m.role == "user")

    def delete_thread_with_messages(self, thread_id: str) -> None:
        def mutate(state: dict) -> None:
            state["threads"].pop(thread_id, None)
            message_ids = [
                message_id
                for message_id, message in state["messages"].items()
                if message["thread_id"] == thread_id
            ]
            for message_id in message_ids:
                state["messages"].pop(message_id, None)

        self._store.update(mutate)

    def reassign_messages_to_thread(self, message_ids: List[str], thread_id: str) -> None:
        message_id_set = set(message_ids)
        if not message_id_set:
            return

        def mutate(state: dict) -> None:
            now = utc_now_iso()
            touched_threads: set[str] = set()
            for message_id in list(state["messages"].keys()):
                if message_id not in message_id_set:
                    continue
                message = state["messages"][message_id]
                touched_threads.add(message["thread_id"])
                message["thread_id"] = thread_id
            touched_threads.add(thread_id)
            for affected_thread_id in touched_threads:
                if affected_thread_id in state["threads"]:
                    state["threads"][affected_thread_id]["updated_at"] = now

        self._store.update(mutate)


class JsonWorkspaceSnapshotRepository(WorkspaceSnapshotRepository):
    def __init__(self, store: JsonStore):
        self._store = store

    def get_snapshot(self) -> dict:
        return self._store.read()

    def restore_snapshot(self, snapshot: dict) -> None:
        self._store.replace(snapshot)


class JsonSettingsRepository(SettingsRepository):
    def __init__(self, store: JsonStore, default_locale: str, supported_locales: tuple[str, ...]):
        self._store = store
        self._default_locale = default_locale
        self._supported_locales = supported_locales

    def get_locale(self) -> str:
        state = self._store.read()
        locale = state["settings"].get("locale", self._default_locale)
        if locale not in self._supported_locales:
            return self._default_locale
        return locale

    def set_locale(self, locale: str) -> None:
        if locale not in self._supported_locales:
            raise ValueError(f"Unsupported locale: {locale}")

        def mutate(state: dict) -> None:
            state["settings"]["locale"] = locale

        self._store.update(mutate)

    def get_active_graph_thread_id(self) -> str:
        state = self._store.read()
        return state["settings"]["active_graph_thread_id"]

    def set_active_graph_thread_id(self, graph_thread_id: str) -> None:
        state = self._store.read()
        if graph_thread_id not in state["graph_threads"]:
            raise ValueError(f"Graph thread not found: {graph_thread_id}")

        def mutate(state: dict) -> None:
            state["settings"]["active_graph_thread_id"] = graph_thread_id

        self._store.update(mutate)
