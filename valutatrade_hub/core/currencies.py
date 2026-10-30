"""Иерархия валют: базовый класс Currency и наследники Fiat/Crypto (п. 3.1)."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError


class Currency(ABC):
    """Базовая валюта: человекочитаемое имя и код (ТЗ 3.1)."""

    def __init__(self, name: str, code: str) -> None:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        code_normalized = code.strip().upper()
        if not (2 <= len(code_normalized) <= 5) or not code_normalized.isalnum():
            raise ValueError(f"Код валюты должен быть 2–5 символов, без пробелов: '{code}'")
        self.name: str = name
        self.code: str = code_normalized

    @abstractmethod
    def get_display_info(self) -> str:
        """Возвращает строковое представление валюты для UI/логов."""


class FiatCurrency(Currency):
    """Фиатная валюта: дополнительно страна (зона) эмиссии."""

    def __init__(self, name: str, code: str, issuing_country: str) -> None:
        super().__init__(name=name, code=code)
        if not isinstance(issuing_country, str) or not issuing_country.strip():
            raise ValueError("Страна эмиссии не может быть пустой")
        self.issuing_country: str = issuing_country

    def get_display_info(self) -> str:
        """Возвращает строку вида «[FIAT] USD — US Dollar (Issuing: United States)»."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта: дополнительно алгоритм майнинга и капитализация."""

    def __init__(self, name: str, code: str, algorithm: str, market_cap: float) -> None:
        super().__init__(name=name, code=code)
        if not isinstance(algorithm, str) or not algorithm.strip():
            raise ValueError("Алгоритм не может быть пустым")
        if not isinstance(market_cap, (int, float)) or market_cap < 0:
            raise ValueError("Капитализация должна быть неотрицательным числом")
        self.algorithm: str = algorithm
        self.market_cap: float = float(market_cap)

    def get_display_info(self) -> str:
        """Возвращает строку вида «[CRYPTO] BTC — Bitcoin (Algo: SHA-256, MCAP: 1.12e12)»."""
        mcap_str = f"{self.market_cap:.2e}".replace("e+", "e")
        return f"[CRYPTO] {self.code} — {self.name} (Algo: {self.algorithm}, MCAP: {mcap_str})"


# Реестр валют: код → объект Currency.
_CURRENCIES: dict[str, Currency] = {
    "USD": FiatCurrency("US Dollar", "USD", "United States"),
    "EUR": FiatCurrency("Euro", "EUR", "Eurozone"),
    "GBP": FiatCurrency("British Pound", "GBP", "United Kingdom"),
    "RUB": FiatCurrency("Russian Ruble", "RUB", "Russia"),
    "BTC": CryptoCurrency("Bitcoin", "BTC", "SHA-256", 1.12e12),
    "ETH": CryptoCurrency("Ethereum", "ETH", "Ethash", 4.03e11),
    "SOL": CryptoCurrency("Solana", "SOL", "Proof of History", 6.7e10),
}


def get_currency(code: str) -> Currency:
    """Возвращает валюту из реестра по коду, иначе бросает CurrencyNotFoundError."""
    if not isinstance(code, str):
        raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")
    normalized = code.strip().upper()
    currency = _CURRENCIES.get(normalized)
    if currency is None:
        raise CurrencyNotFoundError(f"Неизвестная валюта '{code}'")
    return currency
