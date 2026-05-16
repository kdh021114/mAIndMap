from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Dict


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
        state.setdefault("nodes", {})
        state.setdefault("edges", {})
        state.setdefault("threads", {})
        state.setdefault("messages", {})

    def _empty_state(self) -> Dict[str, Any]:
        return {
            "settings": {"locale": "ko"},
            "nodes": {},
            "edges": {},
            "threads": {},
            "messages": {},
        }
