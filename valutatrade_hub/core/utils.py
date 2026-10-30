"""Вспомогательные функции: валидации и форматирование (п. 2.2 и 3.5)."""

from __future__ import annotations

from datetime import UTC, datetime

from valutatrade_hub.core.currencies import get_currency


def utc_timestamp() -> str:
    """Возвращает текущее время в ISO UTC (вид 2025-10-10T12:00:00Z, примеры ТЗ 4.4)."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_amount(amount: float) -> float:
    """Проверяет, что amount — положительное число, и возвращает его как float."""
    try:
        value = float(amount)
    except (TypeError, ValueError) as exc:
        raise ValueError("'amount' должен быть положительным числом") from exc

    if value <= 0:
        raise ValueError("'amount' должен быть положительным числом")

    return value


def validate_currency_code(code: str) -> str:
    """Проверяет код валюты через реестр и возвращает его в верхнем регистре."""
    if not isinstance(code, str) or not code:
        raise ValueError("Код валюты не может быть пустым")

    normalized = code.upper()
    get_currency(normalized)
    return normalized
