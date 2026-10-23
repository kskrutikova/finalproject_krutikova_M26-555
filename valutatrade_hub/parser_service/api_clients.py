"""Клиенты внешних API для Parser Service (п. 4.4)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig


class BaseApiClient(ABC):
    """Базовый интерфейс клиента внешнего API."""

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Вернуть курсы в формате {"BTC_USD": 59337.21, ...}."""


class CoinGeckoClient(BaseApiClient):
    """Клиент CoinGecko для криптовалют."""

    def __init__(self, config: ParserConfig) -> None:
        self._config = config

    def fetch_rates(self) -> dict[str, float]:
        crypto_ids = ",".join(
            self._config.CRYPTO_ID_MAP[code] for code in self._config.CRYPTO_CURRENCIES
        )

        url = self._config.COINGECKO_URL
        params = {
            "ids": crypto_ids,
            "vs_currencies": self._config.BASE_CURRENCY.lower(),
        }

        try:
            response = requests.get(
                url,
                params=params,
                timeout=self._config.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"Ошибка при обращении к CoinGecko: {exc}") from exc

        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise ApiRequestError("CoinGecko вернул некорректный JSON") from exc

        base = self._config.BASE_CURRENCY.lower()
        rates: dict[str, float] = {}

        for code in self._config.CRYPTO_CURRENCIES:
            coin_id = self._config.CRYPTO_ID_MAP[code]
            rate = data.get(coin_id, {}).get(base)

            if not isinstance(rate, (int, float)):
                raise ApiRequestError(f"CoinGecko не вернул курс для {code}")

            rates[f"{code}_{self._config.BASE_CURRENCY}"] = float(rate)

        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API для фиатных валют."""

    def __init__(self, config: ParserConfig) -> None:
        self._config = config

    def fetch_rates(self) -> dict[str, float]:
        if not self._config.EXCHANGERATE_API_KEY:
            raise ApiRequestError(
                "Не задан API-ключ ExchangeRate-API (переменная окружения EXCHANGERATE_API_KEY)"
            )

        url = (
            f"{self._config.EXCHANGERATE_API_URL}/"
            f"{self._config.EXCHANGERATE_API_KEY}/latest/"
            f"{self._config.BASE_CURRENCY}"
        )

        try:
            response = requests.get(
                url,
                timeout=self._config.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(f"Ошибка при обращении к ExchangeRate-API: {exc}") from exc

        try:
            data: dict[str, Any] = response.json()
        except ValueError as exc:
            raise ApiRequestError("ExchangeRate-API вернул некорректный JSON") from exc

        if data.get("result") != "success":
            raise ApiRequestError(
                f"ExchangeRate-API вернул ошибку: {data.get('error-type', 'unknown')}"
            )

        api_rates = data.get("rates", {})
        rates: dict[str, float] = {}

        for code in self._config.FIAT_CURRENCIES:
            rate = api_rates.get(code)

            if not isinstance(rate, (int, float)):
                raise ApiRequestError(f"ExchangeRate-API не вернул курс для {code}")

            # API возвращает стоимость одной USD в валюте code,
            # поэтому для пары CODE_USD выполняем обратное преобразование.
            if rate == 0:
                raise ApiRequestError(f"Некорректный нулевой курс для {code}")

            rates[f"{code}_{self._config.BASE_CURRENCY}"] = 1 / float(rate)

        return rates
