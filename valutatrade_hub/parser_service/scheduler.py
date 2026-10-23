"""Планировщик периодического обновления курсов (п. 4.4)."""

from __future__ import annotations

import time

from valutatrade_hub.logging_config import setup_parser_logging
from valutatrade_hub.parser_service.updater import RatesUpdater, create_default_updater

logger = setup_parser_logging()


class RatesScheduler:
    """Периодически запускает обновление курсов."""

    def __init__(self, updater: RatesUpdater, interval_seconds: int) -> None:
        if interval_seconds <= 0:
            raise ValueError("Интервал обновления должен быть положительным числом")

        self._updater = updater
        self._interval_seconds = interval_seconds

    def run_forever(self) -> None:
        """Запустить бесконечный цикл обновления курсов."""
        logger.info(
            "Starting scheduler: update every %d seconds.",
            self._interval_seconds,
        )

        while True:
            try:
                self._updater.run_update()
            except Exception:
                logger.exception("Unexpected error during rates update")

            time.sleep(self._interval_seconds)


def create_default_scheduler(interval_seconds: int) -> RatesScheduler:
    """Создать планировщик с настройками и клиентами по умолчанию."""
    return RatesScheduler(
        updater=create_default_updater(),
        interval_seconds=interval_seconds,
    )
