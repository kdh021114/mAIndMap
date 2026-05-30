from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, List, Optional, Protocol

from app.domain.chat import ChatThread, Message
from app.domain.graph import GraphEdge, GraphNode, GraphThread


class GraphRepository(ABC):
    @abstractmethod
    def list_graph_threads(self) -> List[GraphThread]: ...

    @abstractmethod
    def get_graph_thread(self, graph_thread_id: str) -> GraphThread: ...

    @abstractmethod
    def save_graph_thread(self, graph_thread: GraphThread) -> GraphThread: ...

    @abstractmethod
    def delete_graph_thread(self, graph_thread_id: str) -> None: ...

    @abstractmethod
    def list_nodes(self, graph_thread_id: str | None = None) -> List[GraphNode]: ...

    @abstractmethod
    def list_edges(self, graph_thread_id: str | None = None) -> List[GraphEdge]: ...

    @abstractmethod
    def get_node(self, node_id: str) -> GraphNode: ...

    @abstractmethod
    def get_node_by_thread(self, thread_id: str) -> GraphNode: ...

    @abstractmethod
    def get_edge_by_target(self, target_node_id: str) -> Optional[GraphEdge]: ...

    @abstractmethod
    def get_edge(self, edge_id: str) -> GraphEdge: ...

    @abstractmethod
    def save_node(self, node: GraphNode) -> GraphNode: ...

    @abstractmethod
    def save_edge(self, edge: GraphEdge) -> GraphEdge: ...

    @abstractmethod
    def delete_edge(self, edge_id: str) -> None: ...

    @abstractmethod
    def delete_subtree(self, root_node_id: str) -> None: ...


class WorkspaceSnapshotRepository(ABC):
    @abstractmethod
    def get_snapshot(self) -> dict[str, Any]: ...

    @abstractmethod
    def restore_snapshot(self, snapshot: dict[str, Any]) -> None: ...


class ChatRepository(ABC):
    @abstractmethod
    def list_threads(self) -> List[ChatThread]: ...

    @abstractmethod
    def get_thread(self, thread_id: str) -> ChatThread: ...

    @abstractmethod
    def save_thread(self, thread: ChatThread) -> ChatThread: ...

    @abstractmethod
    def add_message(self, message: Message) -> Message: ...

    @abstractmethod
    def list_messages(self, thread_id: str) -> List[Message]: ...

    @abstractmethod
    def update_message_content(self, message_id: str, content: str) -> Message: ...

    @abstractmethod
    def delete_messages(self, message_ids: List[str]) -> None: ...

    @abstractmethod
    def count_user_messages(self, thread_id: str) -> int: ...

    @abstractmethod
    def delete_thread_with_messages(self, thread_id: str) -> None: ...

    @abstractmethod
    def reassign_messages_to_thread(self, message_ids: List[str], thread_id: str) -> None: ...


class SettingsRepository(ABC):
    @abstractmethod
    def get_locale(self) -> str: ...

    @abstractmethod
    def set_locale(self, locale: str) -> None: ...

    @abstractmethod
    def get_active_graph_thread_id(self) -> str: ...

    @abstractmethod
    def set_active_graph_thread_id(self, graph_thread_id: str) -> None: ...


class ChatModel(ABC):
    @abstractmethod
    def generate_reply(
        self,
        *,
        system_prompt: str,
        messages: List[Message],
        web_search_enabled: bool = False,
        truncation_notice: Optional[str] = None,
    ) -> str: ...


class EdgePhraseGenerator(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        source_title: str,
        target_title: str,
        first_user_prompt: str,
        locale: str,
    ) -> str: ...


class NodeTitleGenerator(ABC):
    @abstractmethod
    def generate(self, *, first_user_prompt: str, locale: str) -> str: ...
