"""Координация обновления курсов Parser Service (п. 4.4)."""

from __future__ import annotations

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

    def run_update(self) -> dict[str, int]:
        """Обновить курсы. Возвращает количество курсов по каждому клиенту."""
        logger.info("Starting rates update...")

        all_rates: dict[str, float] = {}
        sources: dict[str, str] = {}
        updated_counts: dict[str, int] = {}
        errors: list[str] = []

        for client in self._clients:
            client_name = type(client).__name__

            logger.info("Fetching from %s...", client_name)

            try:
                rates = client.fetch_rates()
            except ApiRequestError as exc:
                logger.error("Failed to fetch from %s: %s", client_name, exc)
                errors.append(f"{client_name}: {exc}")
                continue

            for pair, rate in rates.items():
                all_rates[pair] = rate
                sources[pair] = client_name

            updated_counts[client_name] = len(rates)
            logger.info("Fetching from %s... OK (%d rates)", client_name, len(rates))

        if all_rates:
            self._storage.save_snapshot(all_rates, sources)
            self._storage.append_history(all_rates, sources)
            logger.info(
                "Writing %d rates to %s...",
                len(all_rates),
                self._config.RATES_FILE_PATH,
            )

        if errors:
            logger.error("Update completed with errors: %s", "; ".join(errors))
        else:
            logger.info("Update successful.")

        return updated_counts


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
