"""Абстракция над JSON-хранилищем: Singleton DatabaseManager (п. 3.3, 4.4)"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    _instance: DatabaseManager | None = None

    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_paths()
        return cls._instance

    def _init_paths(self) -> None:
        data_dir = SettingsLoader().get("data_dir", "data")
        # Путь считаем относительно корня проекта (там, где pyproject.toml).
        project_root = Path(__file__).resolve().parents[2]
        self._data_dir = project_root / data_dir

    def _path(self, filename: str) -> Path:
        return self._data_dir / filename

    def read(self, filename: str, default: Any = None) -> Any:

        path = self._path(filename)
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def write(self, filename: str, data: Any) -> None:
        self._data_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(filename)
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, path)
