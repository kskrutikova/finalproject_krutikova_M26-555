"""Клиенты внешних API для Parser Service (п. 4.4)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from http import HTTPStatus
from typing import Any

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.parser_service.config import ParserConfig

# Замена секрета в текстах ошибок и логов.
MASK = "***"


def hide_secret(value: object, secret: str | None) -> str:
    """Убирает секрет из текста: в логах не должно быть API-ключа (ТЗ 4.4)."""
    message = str(value)
    if secret:
        message = message.replace(secret, MASK)
    return message


class BaseApiClient(ABC):
    """Базовый интерфейс клиента внешнего API (п. 4.2)."""

    # Имя источника попадает в source у курсов и в историю (примеры ТЗ 4.4).
    source_name: str = "unknown"

    def __init__(self, config: ParserConfig) -> None:
        self._config = config

    @abstractmethod
    def fetch_rates(self) -> dict[str, float]:
        """Вернуть курсы в формате {"BTC_USD": 59337.21, ...}."""

    def _get_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        secret: str | None = None,
    ) -> dict[str, Any]:
        """Выполняет GET-запрос с таймаутом и возвращает JSON ответа.

        Сообщения об ошибках — по требованиям ТЗ 4.2: 401/403 про API-ключ,
        429 про лимит запросов, 5xx про недоступность сервиса. Сетевые сбои
        и некорректный JSON тоже превращаются в ApiRequestError, чтобы
        RatesUpdater видел единый тип ошибки.

        Имя источника в текст не подставляется: его добавляет вызывающий код
        («Failed to fetch from CoinGecko: …»), иначе оно звучало бы дважды.

        secret — значение, которое не должно попасть в лог: у ExchangeRate-API
        ключ является частью URL, а requests печатает URL в тексте исключения.
        """
        timeout = self._config.REQUEST_TIMEOUT

        try:
            response = requests.get(url, params=params, timeout=timeout)
        except requests.exceptions.Timeout as exc:
            raise ApiRequestError(f"нет ответа за {timeout} с (таймаут)") from exc
        except requests.exceptions.ConnectionError as exc:
            raise ApiRequestError("нет соединения — проверьте доступ в интернет") from exc
        except requests.exceptions.RequestException as exc:
            raise ApiRequestError(hide_secret(exc, secret)) from exc

        status = response.status_code
        if status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN):
            raise ApiRequestError(f"HTTP {status}. Проверьте API-ключ")
        if status == HTTPStatus.TOO_MANY_REQUESTS:
            raise ApiRequestError(f"HTTP {status}. Превышен лимит запросов, повторите позже")
        if status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise ApiRequestError(f"HTTP {status}. Сервис временно недоступен")
        if status != HTTPStatus.OK:
            raise ApiRequestError(f"неожиданный статус ответа HTTP {status}")

        try:
            data = response.json()
        except ValueError as exc:
            raise ApiRequestError("в ответе некорректный JSON") from exc

        if not isinstance(data, dict):
            raise ApiRequestError("неожиданный формат ответа")

        return data


class CoinGeckoClient(BaseApiClient):
    """Клиент CoinGecko для криптовалют."""

    source_name = "CoinGecko"

    def fetch_rates(self) -> dict[str, float]:
        """Запрашивает курсы криптовалют и возвращает {"BTC_USD": 59337.21, ...}."""
        crypto_ids = ",".join(
            self._config.CRYPTO_ID_MAP[code] for code in self._config.CRYPTO_CURRENCIES
        )

        data = self._get_json(
            self._config.COINGECKO_URL,
            params={
                "ids": crypto_ids,
                "vs_currencies": self._config.BASE_CURRENCY.lower(),
            },
        )

        base = self._config.BASE_CURRENCY.lower()
        rates: dict[str, float] = {}

        for code in self._config.CRYPTO_CURRENCIES:
            coin_id = self._config.CRYPTO_ID_MAP[code]
            rate = data.get(coin_id, {}).get(base)

            if not isinstance(rate, (int, float)):
                raise ApiRequestError(f"в ответе нет курса для {code}")

            rates[f"{code}_{self._config.BASE_CURRENCY}"] = float(rate)

        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Клиент ExchangeRate-API для фиатных валют."""

    source_name = "ExchangeRate-API"

    def fetch_rates(self) -> dict[str, float]:
        """Запрашивает курсы фиатных валют и возвращает {"EUR_USD": 1.0786, ...}."""
        if not self._config.EXCHANGERATE_API_KEY:
            raise ApiRequestError("Не задан API-ключ (переменная окружения EXCHANGERATE_API_KEY)")

        url = (
            f"{self._config.EXCHANGERATE_API_URL}/"
            f"{self._config.EXCHANGERATE_API_KEY}/latest/"
            f"{self._config.BASE_CURRENCY}"
        )

        data = self._get_json(url, secret=self._config.EXCHANGERATE_API_KEY)

        if data.get("result") != "success":
            raise ApiRequestError(f"в ответе ошибка: {data.get('error-type', 'unknown')}")

        api_rates = data.get("conversion_rates", {})
        rates: dict[str, float] = {}

        for code in self._config.FIAT_CURRENCIES:
            rate = api_rates.get(code)

            if not isinstance(rate, (int, float)):
                raise ApiRequestError(f"в ответе нет курса для {code}")

            # API возвращает стоимость одной USD в валюте code,
            # поэтому для пары CODE_USD выполняем обратное преобразование.
            if rate == 0:
                raise ApiRequestError(f"Некорректный нулевой курс для {code}")

            rates[f"{code}_{self._config.BASE_CURRENCY}"] = 1 / float(rate)

        return rates
