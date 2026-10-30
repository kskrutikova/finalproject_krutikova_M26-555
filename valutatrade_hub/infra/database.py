"""Абстракция над JSON-хранилищем: Singleton DatabaseManager (п. 3.3, 4.4)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


def read_json(path: Path, default: Any = None) -> Any:
    """Читает JSON-файл по пути; если файла нет — возвращает default."""
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    """Атомарно записывает JSON: временный файл → os.replace (ТЗ 4.4, п. 1)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, path)


class DatabaseManager:
    """Синглтон - абстракция над JSON-хранилищем data/ (п. 3.3).

    Синглтон сделан через __new__: приложение получает один путь к data/
    и один способ чтения/записи без отдельного метакласса.
    """

    _instance: DatabaseManager | None = None

    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_paths()
        return cls._instance

    def _init_paths(self) -> None:
        """Определяет каталог данных из конфигурации SettingsLoader."""
        data_dir = SettingsLoader().get("data_dir", "data")
        # Путь считаем относительно корня проекта (там, где pyproject.toml).
        project_root = Path(__file__).resolve().parents[2]
        self._data_dir = project_root / data_dir

    def data_path(self, filename: str) -> Path:
        """Возвращает полный путь к файлу внутри каталога данных."""
        return self._data_dir / filename

    def read(self, filename: str, default: Any = None) -> Any:
        """Читает JSON-файл хранилища; если файла нет — возвращает default."""
        return read_json(self.data_path(filename), default)

    def write(self, filename: str, data: Any) -> None:
        """Атомарно записывает JSON-файл хранилища."""
        write_json(self.data_path(filename), data)
