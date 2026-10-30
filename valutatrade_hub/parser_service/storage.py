"""Хранилище курсов Parser Service (п. 4.4)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    """Чтение и атомарная запись файлов курсов."""

    def __init__(self, config: ParserConfig) -> None:
        self._config = config

    def _path(self, file_path: str) -> Path:
        """Возвращает путь к файлу курсов."""
        return Path(file_path)

    def _atomic_write(self, path: Path, data: Any) -> None:
        """Пишет JSON атомарно: временный файл → os.replace (ТЗ 4.4, п. 1)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())

        os.replace(tmp_path, path)

    def save_snapshot(self, rates: dict[str, float], sources: dict[str, str]) -> None:
        """Сохранить последние курсы в data/rates.json."""
        now = datetime.now(UTC).isoformat()

        pairs = {
            pair: {
                "rate": rate,
                "updated_at": now,
                "source": sources.get(pair, "unknown"),
            }
            for pair, rate in rates.items()
        }

        snapshot = {
            "pairs": pairs,
            "last_refresh": now,
        }

        self._atomic_write(self._path(self._config.RATES_FILE_PATH), snapshot)

    def append_history(self, rates: dict[str, float], sources: dict[str, str]) -> None:
        """Добавить измерения в data/exchange_rates.json."""
        history_path = self._path(self._config.HISTORY_FILE_PATH)

        if history_path.exists():
            with history_path.open("r", encoding="utf-8") as file:
                history = json.load(file)
        else:
            history = []

        now = datetime.now(UTC).isoformat()

        for pair, rate in rates.items():
            from_code, to_code = pair.split("_", 1)

            record = {
                "id": f"{from_code}{to_code}_{now}",
                "from_currency": from_code,
                "to_currency": to_code,
                "rate": rate,
                "timestamp": now,
                "source": sources.get(pair, "unknown"),
                "meta": {},
            }

            history.append(record)

        self._atomic_write(history_path, history)
