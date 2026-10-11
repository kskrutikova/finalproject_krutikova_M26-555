"""Конфигурация проекта: Singleton SettingsLoader (ТЗ, п. 3.3).

Загружает параметры из секции [tool.valutatrade] в pyproject.toml.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

# Путь к pyproject.toml относительно корня проекта.
# settings.py лежит в valutatrade_hub/infra/, значит поднимаемся на 2 уровня вверх.
_PYPROJECT_PATH = Path(__file__).resolve().parents[2] / "pyproject.toml"


class SettingsLoader:
    """Singleton-загрузчик конфигурации проекта.

    Гарантирует, что в приложении существует ровно один экземпляр.
    Способ реализации — через __new__: он проще и читабельнее метакласса,
    а для нашей задачи (один класс-синглтон) этого достаточно.
    """

    _instance: SettingsLoader | None = None

    def __new__(cls) -> SettingsLoader:
        # Если экземпляр уже создан — возвращаем его,
        # повторной инициализации не будет.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._config: dict[str, Any] = {}
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        """Перезагрузить конфигурацию из pyproject.toml."""
        with _PYPROJECT_PATH.open("rb") as f:
            data = tomllib.load(f)
        self._config = data.get("tool", {}).get("valutatrade", {})
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        """Получить значение параметра конфигурации по ключу."""
        return self._config.get(key, default)
