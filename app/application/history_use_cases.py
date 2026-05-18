from __future__ import annotations

from typing import Any

from app.domain.ports import WorkspaceSnapshotRepository


class GetWorkspaceSnapshotUseCase:
    def __init__(self, snapshot_repository: WorkspaceSnapshotRepository):
        self._snapshot_repository = snapshot_repository

    def execute(self) -> dict[str, Any]:
        return self._snapshot_repository.get_snapshot()


class RestoreWorkspaceSnapshotUseCase:
    def __init__(self, snapshot_repository: WorkspaceSnapshotRepository):
        self._snapshot_repository = snapshot_repository

    def execute(self, *, snapshot: dict[str, Any]) -> None:
        self._snapshot_repository.restore_snapshot(snapshot)
