"""Конфигурация Parser Service (п. 4.4).

Чувствительные данные (API-ключ ExchangeRate-API) загружаются
из переменной окружения и не хранятся в коде или Git.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class ParserConfig:
    """Настройки Parser Service."""

    # Ключ ExchangeRate-API загружается из переменной окружения.
    EXCHANGERATE_API_KEY: str | None = os.getenv("EXCHANGERATE_API_KEY")

    # Эндпоинты внешних API.
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"

    # Базовая валюта для запросов и хранения курсов.
    BASE_CURRENCY: str = "USD"

    # Фиатные валюты для отслеживания.
    FIAT_CURRENCIES: tuple[str, ...] = ("EUR", "GBP", "RUB")

    # Криптовалюты для отслеживания.
    CRYPTO_CURRENCIES: tuple[str, ...] = ("BTC", "ETH", "SOL")

    # Соответствие тикеров криптовалют и ID CoinGecko.
    # ClassVar: это постоянный словарь настроек, а не данные экземпляра.
    CRYPTO_ID_MAP: ClassVar[dict[str, str]] = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
    }

    # Пути к файлам Parser Service и Core Service.
    RATES_FILE_PATH: str = "data/rates.json"
    HISTORY_FILE_PATH: str = "data/exchange_rates.json"

    # Сетевые параметры.
    REQUEST_TIMEOUT: int = 10
