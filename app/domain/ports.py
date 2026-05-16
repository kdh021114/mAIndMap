from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Protocol

from app.domain.chat import ChatThread, Message
from app.domain.graph import GraphEdge, GraphNode


class GraphRepository(ABC):
    @abstractmethod
    def list_nodes(self) -> List[GraphNode]: ...

    @abstractmethod
    def list_edges(self) -> List[GraphEdge]: ...

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
    def delete_subtree(self, root_node_id: str) -> None: ...


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
    def count_user_messages(self, thread_id: str) -> int: ...

    @abstractmethod
    def delete_thread_with_messages(self, thread_id: str) -> None: ...


class SettingsRepository(ABC):
    @abstractmethod
    def get_locale(self) -> str: ...

    @abstractmethod
    def set_locale(self, locale: str) -> None: ...


class ChatModel(ABC):
    @abstractmethod
    def generate_reply(self, *, system_prompt: str, messages: List[Message]) -> str: ...


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
