from __future__ import annotations

from app.application.localization import pick_localized_text
from app.domain.ports import ChatRepository, GraphRepository, SettingsRepository
from app.infrastructure.layout.tree_layout_service import TreeLayoutService


class GetWorkspaceStateUseCase:
    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        settings_repository: SettingsRepository,
        layout_service: TreeLayoutService,
        app_title: str,
        llm_mode: str,
        web_search_available: bool,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._settings_repository = settings_repository
        self._layout_service = layout_service
        self._app_title = app_title
        self._llm_mode = llm_mode
        self._web_search_available = web_search_available

    def execute(self) -> dict:
        locale = self._settings_repository.get_locale()
        active_graph_thread_id = self._settings_repository.get_active_graph_thread_id()
        graph_threads = self._graph_repository.list_graph_threads()
        nodes = self._graph_repository.list_nodes(graph_thread_id=active_graph_thread_id)
        edges = self._graph_repository.list_edges(graph_thread_id=active_graph_thread_id)
        layout = self._layout_service.layout(nodes)
        children_count = {node.id: 0 for node in nodes}
        for node in nodes:
            if node.parent_node_id in children_count:
                children_count[node.parent_node_id] += 1
        depths = self._node_depths(nodes)
        message_stats = self._message_stats(nodes)

        return {
            "appTitle": self._app_title,
            "locale": locale,
            "llmMode": self._llm_mode,
            "usingMockLlm": self._llm_mode in {"test", "mock"},
            "webSearchAvailable": self._web_search_available,
            "activeGraphThreadId": active_graph_thread_id,
            "graphThreads": [
                self._graph_thread_state(
                    graph_thread=graph_thread,
                    locale=locale,
                    is_active=graph_thread.id == active_graph_thread_id,
                )
                for graph_thread in graph_threads
            ],
            "graphSettings": self._layout_service.settings(),
            "nodes": [
                {
                    "id": node.id,
                    "graphThreadId": node.graph_thread_id,
                    "threadId": node.thread_id,
                    "parentNodeId": node.parent_node_id,
                    "title": node.title,
                    "displayTitle": pick_localized_text(node.title, locale, fallback="Untitled"),
                    "position": {"x": node.position.x, "y": node.position.y},
                    "manuallyPositioned": node.manually_positioned,
                    "layout": layout.get(node.id, {"x": 0, "y": 0, "width": 210, "height": 82}),
                    "depth": depths.get(node.id, 0),
                    "childrenCount": children_count.get(node.id, 0),
                    "messageCount": message_stats[node.id]["count"],
                    "userMessageCount": message_stats[node.id]["user_count"],
                    "messageTextLength": message_stats[node.id]["text_length"],
                    "createdAt": node.created_at,
                    "updatedAt": node.updated_at,
                }
                for node in nodes
            ],
            "edges": [
                {
                    "id": edge.id,
                    "graphThreadId": edge.graph_thread_id,
                    "sourceNodeId": edge.source_node_id,
                    "targetNodeId": edge.target_node_id,
                    "phrase": edge.phrase,
                    "displayPhrase": pick_localized_text(edge.phrase, locale, fallback=""),
                    "phraseGeneratedBy": edge.phrase_generated_by,
                    "createdAt": edge.created_at,
                    "updatedAt": edge.updated_at,
                }
                for edge in edges
            ],
        }

    def _graph_thread_state(self, *, graph_thread, locale: str, is_active: bool) -> dict:
        nodes = self._graph_repository.list_nodes(graph_thread_id=graph_thread.id)
        root = next((node for node in nodes if node.parent_node_id is None), None)
        display_title = pick_localized_text(graph_thread.title, locale, fallback="Graph thread")
        if root is not None:
            display_title = pick_localized_text(root.title, locale, fallback=display_title)
        message_count = sum(len(self._chat_repository.list_messages(node.thread_id)) for node in nodes)
        return {
            "id": graph_thread.id,
            "title": graph_thread.title,
            "displayTitle": display_title,
            "nodeCount": len(nodes),
            "messageCount": message_count,
            "isActive": is_active,
            "createdAt": graph_thread.created_at,
            "updatedAt": graph_thread.updated_at,
        }

    def _node_depths(self, nodes) -> dict[str, int]:
        by_id = {node.id: node for node in nodes}
        depths: dict[str, int] = {}

        def depth_of(node) -> int:
            if node.id in depths:
                return depths[node.id]
            if node.parent_node_id is None or node.parent_node_id not in by_id:
                depths[node.id] = 0
                return 0
            depths[node.id] = depth_of(by_id[node.parent_node_id]) + 1
            return depths[node.id]

        for node in nodes:
            depth_of(node)
        return depths

    def _message_stats(self, nodes) -> dict[str, dict[str, int]]:
        stats = {}
        for node in nodes:
            messages = self._chat_repository.list_messages(node.thread_id)
            stats[node.id] = {
                "count": len(messages),
                "user_count": sum(1 for message in messages if message.role == "user"),
                "text_length": sum(len(message.content) for message in messages),
            }
        return stats
