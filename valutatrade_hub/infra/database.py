"""Абстракция над JSON-хранилищем: Singleton DatabaseManager (ТЗ, п. 3.3).

Предоставляет безопасные операции чтения и записи JSON-файлов
из каталога data/. Запись выполняется атомарно (tmp → rename),
как требует ТЗ (п. 4.4).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Singleton-менеджер JSON-хранилища.

    Гарантирует, что в приложении существует ровно один экземпляр.
    Способ реализации — через __new__ (как в SettingsLoader):
    проще и читабельнее метакласса, для нашей задачи достаточно.
    """

    _instance: DatabaseManager | None = None

    def __new__(cls) -> DatabaseManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_paths()
        return cls._instance

    def _init_paths(self) -> None:
        """Определить путь к каталогу data/ по конфигурации."""
        data_dir = SettingsLoader().get("data_dir", "data")
        # Путь считаем относительно корня проекта (там, где pyproject.toml).
        project_root = Path(__file__).resolve().parents[2]
        self._data_dir = project_root / data_dir

    def _path(self, filename: str) -> Path:
        """Полный путь к JSON-файлу внутри data/."""
        return self._data_dir / filename

    def read(self, filename: str, default: Any = None) -> Any:
        """Прочитать JSON-файл из data/.

        Если файла нет — вернуть default (по умолчанию None).
        Пустые файлы не создаются автоматически.
        """
        path = self._path(filename)
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def write(self, filename: str, data: Any) -> None:
        """Атомарно записать данные в JSON-файл внутри data/.

        Алгоритм: пишем во временный файл, затем os.replace().
        os.replace атомарен в пределах одной файловой системы,
        поэтому читатель никогда не увидит半-записанный файл.
        """
        self._data_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(filename)
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp_path, path)
