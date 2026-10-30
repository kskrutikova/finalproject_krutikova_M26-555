"""Хранилище курсов Parser Service: rates.json и история измерений (п. 4.4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from valutatrade_hub.core.utils import utc_timestamp
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig

# Источник для пары, если клиент его не назвал.
_UNKNOWN_SOURCE = "unknown"


class RatesStorage:
    """Чтение и запись файлов курсов через JSON-хранилище приложения."""

    def __init__(self, config: ParserConfig) -> None:
        self._config = config
        # DatabaseManager сам ищет файлы в каталоге data из конфигурации,
        # поэтому здесь только имена: Parser Service и Core Service обязаны
        # видеть один и тот же rates.json при любом рабочем каталоге.
        self._db = DatabaseManager()
        self._rates_file = Path(config.RATES_FILE_PATH).name
        self._history_file = Path(config.HISTORY_FILE_PATH).name

    def read_snapshot(self) -> dict[str, Any]:
        """Возвращает снимок курсов из rates.json (пустой словарь, если файла нет)."""
        return self._db.read(self._rates_file, default=None) or {}

    def save_snapshot(self, rates: dict[str, float], sources: dict[str, str]) -> None:
        """Сохраняет последние курсы в rates.json.

        Курсы только что получены от API, поэтому они новее сохраненных и
        перезаписывают свою пару. Пары, которых нет в этом обновлении
        (например, при update-rates --source coingecko), остаются без
        изменений — по ТЗ «апдейт побеждает, если updated_at свежее текущего».
        """
        now = utc_timestamp()
        pairs: dict[str, Any] = dict(self.read_snapshot().get("pairs", {}))

        for pair, rate in rates.items():
            pairs[pair] = {
                "rate": rate,
                "updated_at": now,
                "source": sources.get(pair, _UNKNOWN_SOURCE),
            }

        self._db.write(self._rates_file, {"pairs": pairs, "last_refresh": now})

    def append_history(self, rates: dict[str, float], sources: dict[str, str]) -> None:
        """Добавляет замеры в историю exchange_rates.json.

        Идентификатор записи собирается из пары и времени замера
        (BTC_USD_2025-10-10T12:00:00Z), поэтому уже сохраненный замер
        того же времени не удваивает историю.
        """
        history = self._db.read(self._history_file, default=[])
        if not isinstance(history, list):
            history = []

        known_ids = {record.get("id") for record in history}
        timestamp = utc_timestamp()

        for pair, rate in rates.items():
            from_code, to_code = pair.split("_", 1)
            record_id = f"{from_code}_{to_code}_{timestamp}"

            if record_id in known_ids:
                continue

            history.append(
                {
                    "id": record_id,
                    "from_currency": from_code,
                    "to_currency": to_code,
                    "rate": rate,
                    "timestamp": timestamp,
                    "source": sources.get(pair, _UNKNOWN_SOURCE),
                    "meta": {},
                }
            )
            known_ids.add(record_id)

        self._db.write(self._history_file, history)
