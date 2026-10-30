"""Декоратор @log_action - логирование доменных операций (п. 3.4).

Пишет INFO-строку в logs/actions.log через логгер из logging_config.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from valutatrade_hub.logging_config import setup_logging

# Поля, которые декоратор ищет в kwargs декорируемой функции.
# Имена соответствуют сигнатурам usecases из ТЗ 3.5
# (buy/sell/get_rate/register/login).
_FIELD_ORDER = ("user_id", "username", "currency_code", "amount", "rate", "base")


def _format_field(name: str, value: Any) -> str:
    """Форматирует одно поле логи, строки в кавычках, суммы с точностью."""
    if name == "amount":
        try:
            return f"{name}={float(value):.4f}"
        except (TypeError, ValueError):
            return f"{name}='{value}'"

    if isinstance(value, str):
        return f"{name}='{value}'"

    if name in ("rate", "before", "after"):
        return f"{name}={value:.4f}"

    return f"{name}={value}"


def log_action(action: str, verbose: bool = False) -> Callable:
    """Логирует доменную операцию на уровне INFO и не глотает исключения.

    Args:
        action: метка операции (BUY, SELL, REGISTER, LOGIN).
        verbose: добавлять в лог состояние кошелька «было --> стало».
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = setup_logging()
            parts: list[str] = [action]

            for name in _FIELD_ORDER:
                if name in kwargs:
                    parts.append(_format_field(name, kwargs[name]))

            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                parts.append("result=ERROR")
                parts.append(f"error_type={type(exc).__name__}")
                parts.append(f"error_message='{exc}'")
                logger.info(" ".join(parts))
                raise

            parts.append("result=OK")

            if isinstance(result, dict):
                if "rate" in result:
                    parts.append(_format_field("rate", result["rate"]))
                if "base" in result:
                    parts.append(_format_field("base", result["base"]))

                if verbose and "before" in result and "after" in result:
                    parts.append(_format_field("before", result["before"]))
                    parts.append(_format_field("after", result["after"]))

            logger.info(" ".join(parts))
            return result

        return wrapper

    return decorator
