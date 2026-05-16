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
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._settings_repository = settings_repository
        self._layout_service = layout_service
        self._app_title = app_title
        self._llm_mode = llm_mode

    def execute(self) -> dict:
        locale = self._settings_repository.get_locale()
        nodes = self._graph_repository.list_nodes()
        edges = self._graph_repository.list_edges()
        layout = self._layout_service.layout(nodes)
        children_count = {node.id: 0 for node in nodes}
        for node in nodes:
            if node.parent_node_id in children_count:
                children_count[node.parent_node_id] += 1
        depths = self._node_depths(nodes)

        return {
            "appTitle": self._app_title,
            "locale": locale,
            "llmMode": self._llm_mode,
            "usingMockLlm": self._llm_mode in {"test", "mock"},
            "graphSettings": self._layout_service.settings(),
            "nodes": [
                {
                    "id": node.id,
                    "threadId": node.thread_id,
                    "parentNodeId": node.parent_node_id,
                    "title": node.title,
                    "displayTitle": pick_localized_text(node.title, locale, fallback="Untitled"),
                    "position": {"x": node.position.x, "y": node.position.y},
                    "layout": layout.get(node.id, {"x": 0, "y": 0, "width": 210, "height": 82}),
                    "depth": depths.get(node.id, 0),
                    "childrenCount": children_count.get(node.id, 0),
                    "messageCount": len(self._chat_repository.list_messages(node.thread_id)),
                    "createdAt": node.created_at,
                    "updatedAt": node.updated_at,
                }
                for node in nodes
            ],
            "edges": [
                {
                    "id": edge.id,
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
