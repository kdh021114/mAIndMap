from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict

from app.domain.graph import DEFAULT_GRAPH_THREAD_ID


class JsonStore:
    """Small JSON-backed store for the prototype.

    Repositories depend on this store, while application use cases depend only on
    repository interfaces. This keeps storage replaceable later.
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.RLock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write(self._empty_state())

    def read(self) -> Dict[str, Any]:
        with self._lock:
            return deepcopy(self._read())

    def update(self, mutator: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        with self._lock:
            state = self._read()
            mutator(state)
            self._write(state)
            return deepcopy(state)

    def replace(self, state: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            next_state = deepcopy(state)
            self._ensure_shape(next_state)
            self._write(next_state)
            return deepcopy(next_state)

    def _read(self) -> Dict[str, Any]:
        try:
            with self._path.open("r", encoding="utf-8") as f:
                state = json.load(f)
        except json.JSONDecodeError:
            state = self._empty_state()
        self._ensure_shape(state)
        return state

    def _write(self, state: Dict[str, Any]) -> None:
        tmp_path = self._path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        tmp_path.replace(self._path)

    def _ensure_shape(self, state: Dict[str, Any]) -> None:
        state.setdefault("settings", {"locale": "ko"})
        state.setdefault("graph_threads", {})
        state.setdefault("nodes", {})
        state.setdefault("edges", {})
        state.setdefault("threads", {})
        state.setdefault("messages", {})
        self._ensure_default_graph_thread(state)
        self._ensure_graph_ownership(state)
        self._ensure_active_graph_thread(state)

    def _empty_state(self) -> Dict[str, Any]:
        return {
            "settings": {"locale": "ko", "active_graph_thread_id": DEFAULT_GRAPH_THREAD_ID},
            "graph_threads": {},
            "nodes": {},
            "edges": {},
            "threads": {},
            "messages": {},
        }

    def _ensure_default_graph_thread(self, state: Dict[str, Any]) -> None:
        if state["graph_threads"]:
            return
        state["graph_threads"][DEFAULT_GRAPH_THREAD_ID] = {
            "id": DEFAULT_GRAPH_THREAD_ID,
            "title": {"ko": "기본 스레드", "en": "Default thread"},
            "created_at": "1970-01-01T00:00:00+00:00",
            "updated_at": "1970-01-01T00:00:00+00:00",
        }

    def _ensure_graph_ownership(self, state: Dict[str, Any]) -> None:
        for node in state["nodes"].values():
            node.setdefault("graph_thread_id", DEFAULT_GRAPH_THREAD_ID)
            node.setdefault("manually_positioned", False)
        for edge in state["edges"].values():
            edge.setdefault("graph_thread_id", DEFAULT_GRAPH_THREAD_ID)

    def _ensure_active_graph_thread(self, state: Dict[str, Any]) -> None:
        active_id = state["settings"].get("active_graph_thread_id")
        if active_id in state["graph_threads"]:
            return
        state["settings"]["active_graph_thread_id"] = next(iter(state["graph_threads"]))
