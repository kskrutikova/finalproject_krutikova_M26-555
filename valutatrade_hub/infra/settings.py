"""Конфигурация проекта: Singleton SettingsLoader (п. 3.3).
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
    """Синглтон конфигурации проекта (п. 3.3).

    Синглтон сделан через __new__ экземпляр создается один раз,
    поэтому повторные вызовы SettingsLoader() в модулях возвращают
    уже загруженную конфигурацию.
    """

    _instance: SettingsLoader | None = None

    def __new__(cls) -> SettingsLoader:
        # Если экземпляр уже создан, то возвращаем его,
        # повторной инициализации не будет.
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._config: dict[str, Any] = {}
            cls._instance.reload()
        return cls._instance

    def reload(self) -> None:
        """Заново читает конфигурацию из pyproject.toml."""
        with _PYPROJECT_PATH.open("rb") as f:
            data = tomllib.load(f)
        self._config = data.get("tool", {}).get("valutatrade", {})
        self._loaded = True

    def get(self, key: str, default: Any = None) -> Any:
        """Возвращает параметр конфигурации или default, если ключа нет."""
        return self._config.get(key, default)
