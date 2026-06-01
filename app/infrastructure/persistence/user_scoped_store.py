from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

from app.infrastructure.persistence.json_store import JsonStore


class UserScopedJsonStore:
    """A thin wrapper that keeps one JsonStore per participant, per process.

    All read/update/replace calls are delegated to the participant-specific
    JsonStore whose file lives at <users_dir>/<participant_id>/data.json.

    The participant_id is resolved lazily on every call via a callable so that
    each HTTP request automatically lands in the right store without any
    cross-request state.
    """

    def __init__(self, users_dir: Path, get_participant_id: Callable[[], str]):
        self._users_dir = users_dir
        self._get_participant_id = get_participant_id
        self._stores: Dict[str, JsonStore] = {}

    # ------------------------------------------------------------------
    # Public API — identical to JsonStore so all repositories work as-is
    # ------------------------------------------------------------------

    def read(self) -> Dict[str, Any]:
        return self._store().read()

    def update(self, mutator: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        return self._store().update(mutator)

    def replace(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return self._store().replace(state)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _store(self) -> JsonStore:
        participant_id = self._get_participant_id()
        if participant_id not in self._stores:
            path = self._users_dir / participant_id / "data.json"
            self._stores[participant_id] = JsonStore(path)
        return self._stores[participant_id]
