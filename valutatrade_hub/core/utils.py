"""Вспомогательные функции: валидации (ТЗ, п. 2.2 и 3.5)."""

from __future__ import annotations

from valutatrade_hub.core.currencies import get_currency


def validate_amount(amount: float) -> float:
    """Проверить, что amount — положительное число.

    Возвращает приведённый к float amount.
    Бросает ValueError с понятным сообщением при нарушении.
    """
    try:
        value = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("'amount' должен быть положительным числом") from exc

    if value <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    return value


def validate_currency_code(code: str) -> str:
    """Проверить код валюты и вернуть его в верхнем регистре.

    Если код неизвестен — get_currency бросит CurrencyNotFoundError.
    """
    if not isinstance(code, str) or not code:
        raise ValueError("Код валюты не может быть пустым")

    normalized = code.upper()
    get_currency(normalized)
    return normalized
