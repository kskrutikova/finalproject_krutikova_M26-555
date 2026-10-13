"""Вспомогательные функции: валидации (п. 2.2 и 3.5)"""

from __future__ import annotations

from valutatrade_hub.core.currencies import get_currency


def validate_amount(amount: float) -> float:
    try:
        value = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("'amount' должен быть положительным числом") from exc

    if value <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    return value


def validate_currency_code(code: str) -> str:
    if not isinstance(code, str) or not code:
        raise ValueError("Код валюты не может быть пустым")

    normalized = code.upper()
    get_currency(normalized)
    return normalized
