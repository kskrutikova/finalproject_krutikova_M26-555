"""Декоратор @log_action — логирование доменных операций
Пишет INFO-строку в logs/actions.log через логгер из logging_config."""

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
    if isinstance(value, str):
        return f"{name}='{value}'"
    if name in ("amount", "rate", "before", "after"):
        return f"{name}={value:.4f}"
    return f"{name}={value}"


def log_action(action: str, verbose: bool = False) -> Callable:

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

            # verbose: если функция вернула before/after — добавляем контекст.
            # verbose: если функция вернула before/after — добавляем контекст.
            if verbose and isinstance(result, dict) and "before" in result and "after" in result:
                parts.append(_format_field("before", result["before"]))
                parts.append(_format_field("after", result["after"]))

            logger.info(" ".join(parts))
            return result

        return wrapper

    return decorator
