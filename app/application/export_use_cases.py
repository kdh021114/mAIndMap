from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from app.application.localization import pick_localized_text
from app.domain.common import utc_now_iso
from app.domain.ports import ChatRepository, GraphRepository, SettingsRepository


# How each stored message role is reported as a "speaker" in the export.
_SPEAKER_BY_ROLE = {"user": "user", "assistant": "LLM", "system": "system"}


class ExportThreadLogsUseCase:
    """Build a per-thread export of the whole workspace conversation tree.

    For every thread (graph node) it captures where the thread sits in the tree
    — its level/depth, the order it was created among its siblings, and the
    sibling set — together with the conversation messages and who spoke each one
    (user vs. LLM). The web route packages these entries into a downloadable zip,
    one JSON file per thread.
    """

    def __init__(
        self,
        graph_repository: GraphRepository,
        chat_repository: ChatRepository,
        settings_repository: SettingsRepository,
    ):
        self._graph_repository = graph_repository
        self._chat_repository = chat_repository
        self._settings_repository = settings_repository

    def execute(self) -> Dict[str, Any]:
        locale = self._settings_repository.get_locale()
        exported_at = utc_now_iso()
        graph_threads = self._graph_repository.list_graph_threads()

        entries: List[Dict[str, Any]] = []
        manifest_graphs: List[Dict[str, Any]] = []
        order = 0

        for graph_index, graph_thread in enumerate(graph_threads, start=1):
            graph_title = pick_localized_text(graph_thread.title, locale, fallback="Graph thread")
            nodes = self._graph_repository.list_nodes(graph_thread_id=graph_thread.id)
            by_id = {node.id: node for node in nodes}

            # Direct children grouped by (normalized) parent, ordered by creation
            # time so each node's position among its siblings is deterministic.
            children_by_parent: Dict[Optional[str], List] = {}
            for node in nodes:
                parent = node.parent_node_id if node.parent_node_id in by_id else None
                children_by_parent.setdefault(parent, []).append(node)
            for siblings in children_by_parent.values():
                siblings.sort(key=lambda n: (n.created_at, n.id))

            depth_of = self._depth_resolver(by_id)

            # Nodes grouped by depth, ordered by creation, so we can also report
            # the creation order within a whole tree level (not just siblings).
            nodes_by_level: Dict[int, List] = {}
            for node in nodes:
                nodes_by_level.setdefault(depth_of(node.id), []).append(node)
            for level_nodes in nodes_by_level.values():
                level_nodes.sort(key=lambda n: (n.created_at, n.id))

            manifest_nodes: List[Dict[str, Any]] = []

            # Breadth-first from the roots so files come out parent-before-child
            # with sibling order preserved. Every node is reachable this way
            # because a node's normalized parent is either None (a root) or an
            # existing node id, and the tree is acyclic.
            queue = list(children_by_parent.get(None, []))
            while queue:
                node = queue.pop(0)
                order += 1
                parent = node.parent_node_id if node.parent_node_id in by_id else None
                siblings = children_by_parent.get(parent, [])
                level = depth_of(node.id)
                level_nodes = nodes_by_level.get(level, [])
                children = children_by_parent.get(node.id, [])
                parent_node = by_id.get(parent) if parent else None

                node_title = pick_localized_text(node.title, locale, fallback="Untitled")
                thread = self._safe_thread(node.thread_id)
                thread_title = (
                    pick_localized_text(thread.title, locale, fallback=node_title)
                    if thread is not None
                    else node_title
                )

                messages = self._chat_repository.list_messages(node.thread_id)
                message_dicts = [
                    {
                        "index": i,
                        "role": message.role,
                        "speaker": _SPEAKER_BY_ROLE.get(message.role, message.role),
                        "content": message.content,
                        "created_at": message.created_at,
                    }
                    for i, message in enumerate(messages, start=1)
                ]

                sibling_dicts = [
                    {
                        "node_id": sibling.id,
                        "thread_id": sibling.thread_id,
                        "title": pick_localized_text(sibling.title, locale, fallback="Untitled"),
                        "created_at": sibling.created_at,
                        "is_self": sibling.id == node.id,
                    }
                    for sibling in siblings
                ]

                data = {
                    "schema": "thread-log/v1",
                    "exported_at": exported_at,
                    "locale": locale,
                    "order": order,
                    "graph_thread": {
                        "id": graph_thread.id,
                        "title": graph_title,
                        "index": graph_index,
                    },
                    "thread": {
                        "id": node.thread_id,
                        "title": thread_title,
                        "node_id": node.id,
                        "node_title": node_title,
                        "created_at": node.created_at,
                        "updated_at": node.updated_at,
                    },
                    "tree": {
                        "level": level,
                        "is_root": parent is None,
                        "parent_node_id": parent,
                        "parent_thread_id": parent_node.thread_id if parent_node else None,
                        # 1-based order this node was created among its siblings.
                        "sibling_index": siblings.index(node) + 1,
                        "sibling_count": len(siblings),
                        # 1-based order among all nodes sharing the same tree level.
                        "level_index": level_nodes.index(node) + 1,
                        "level_count": len(level_nodes),
                        "siblings": sibling_dicts,
                        "child_node_ids": [child.id for child in children],
                    },
                    "message_count": len(message_dicts),
                    "messages": message_dicts,
                }

                entries.append(
                    {
                        "order": order,
                        "graph_index": graph_index,
                        "title": thread_title,
                        "thread_id": node.thread_id,
                        "node_id": node.id,
                        "data": data,
                    }
                )
                manifest_nodes.append(
                    {
                        "order": order,
                        "node_id": node.id,
                        "thread_id": node.thread_id,
                        "title": thread_title,
                        "level": level,
                        "sibling_index": siblings.index(node) + 1,
                        "parent_node_id": parent,
                        "message_count": len(message_dicts),
                    }
                )

                queue.extend(children)

            manifest_graphs.append(
                {
                    "id": graph_thread.id,
                    "title": graph_title,
                    "index": graph_index,
                    "node_count": len(nodes),
                    "nodes": manifest_nodes,
                }
            )

        manifest = {
            "schema": "thread-log-index/v1",
            "exported_at": exported_at,
            "locale": locale,
            "graph_thread_count": len(graph_threads),
            "thread_count": len(entries),
            "graphs": manifest_graphs,
        }

        return {
            "exported_at": exported_at,
            "locale": locale,
            "entries": entries,
            "manifest": manifest,
        }

    def _depth_resolver(self, by_id: Dict[str, Any]) -> Callable[[str], int]:
        cache: Dict[str, int] = {}

        def depth(node_id: str) -> int:
            if node_id in cache:
                return cache[node_id]
            parent = by_id[node_id].parent_node_id
            if parent is None or parent not in by_id:
                cache[node_id] = 0
            else:
                cache[node_id] = depth(parent) + 1
            return cache[node_id]

        return depth

    def _safe_thread(self, thread_id: str):
        try:
            return self._chat_repository.get_thread(thread_id)
        except KeyError:
            return None
