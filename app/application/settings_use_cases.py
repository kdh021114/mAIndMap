from __future__ import annotations

from app.domain.ports import SettingsRepository


class ChangeLocaleUseCase:
    def __init__(self, settings_repository: SettingsRepository):
        self._settings_repository = settings_repository

    def execute(self, *, locale: str) -> None:
        self._settings_repository.set_locale(locale)
