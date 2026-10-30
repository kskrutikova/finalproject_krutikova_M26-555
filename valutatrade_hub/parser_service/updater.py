"""Координация обновления курсов Parser Service (п. 4.4)."""

from __future__ import annotations

from dataclasses import dataclass, field

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.logging_config import setup_parser_logging
from valutatrade_hub.parser_service.api_clients import (
    BaseApiClient,
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage

logger = setup_parser_logging()


@dataclass
class SourceOutcome:
    """Результат обращения к одному источнику курсов.

    Нужен не только логу, но и CLI: по этим данным update-rates печатает
    строку «Fetching from … OK (N rates)» или «Failed to fetch from …».
    """

    source: str
    rates: int = 0
    error: str | None = None


@dataclass
class UpdateReport:
    """Итог обновления курсов: отчет для CLI (пример вывода в ТЗ 4.4)."""

    outcomes: list[SourceOutcome] = field(default_factory=list)
    last_refresh: str | None = None

    @property
    def total(self) -> int:
        """Суммарное количество обновленных курсов."""
        return sum(outcome.rates for outcome in self.outcomes)

    @property
    def errors(self) -> list[str]:
        """Сообщения источников, которые не отдали курсы."""
        return [outcome.error for outcome in self.outcomes if outcome.error]

    @property
    def has_errors(self) -> bool:
        """Были ли ошибки хотя бы у одного источника."""
        return bool(self.errors)


class RatesUpdater:
    """Получает курсы у API-клиентов и сохраняет их в хранилище."""

    def __init__(
        self,
        config: ParserConfig,
        clients: list[BaseApiClient],
        storage: RatesStorage,
    ) -> None:
        self._config = config
        self._clients = clients
        self._storage = storage

    def run_update(self) -> UpdateReport:
        """Обновить курсы и вернуть отчет для вызывающего кода.

        Ошибка одного источника не отменяет обновление: курсы остальных
        источников все равно сохраняются, а по отчету CLI честно сообщает о
        частичном сбое (примеры «Update completed with errors» в ТЗ 4.4).
        """
        logger.info("Starting rates update...")

        all_rates: dict[str, float] = {}
        sources: dict[str, str] = {}
        outcomes: list[SourceOutcome] = []

        for client in self._clients:
            source_name = client.source_name

            logger.info("Fetching from %s...", source_name)

            try:
                rates = client.fetch_rates()
            except ApiRequestError as exc:
                logger.error("Failed to fetch from %s: %s", source_name, exc)
                outcomes.append(SourceOutcome(source=source_name, error=str(exc)))
                continue

            for pair, rate in rates.items():
                all_rates[pair] = rate
                sources[pair] = source_name

            updated_counts = len(rates)
            logger.info("Fetching from %s... OK (%d rates)", source_name, updated_counts)
            outcomes.append(SourceOutcome(source=source_name, rates=updated_counts))

        last_refresh = None
        if all_rates:
            logger.info(
                "Writing %d rates to %s...",
                len(all_rates),
                self._config.RATES_FILE_PATH,
            )
            last_refresh = self._storage.save_snapshot(all_rates, sources)
            self._storage.append_history(all_rates, sources)

        report = UpdateReport(outcomes=outcomes, last_refresh=last_refresh)

        if report.has_errors:
            logger.error("Update completed with errors: %s", "; ".join(report.errors))
        else:
            logger.info("Update successful.")

        return report


def create_default_updater() -> RatesUpdater:
    """Создать обновлятель с настройками и клиентами по умолчанию."""
    config = ParserConfig()

    clients: list[BaseApiClient] = [
        CoinGeckoClient(config),
        ExchangeRateApiClient(config),
    ]

    return RatesUpdater(
        config=config,
        clients=clients,
        storage=RatesStorage(config),
    )
