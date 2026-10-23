"""Бизнес-логика: usecases (п. 2.2, 3.5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.models import EXCHANGE_RATES, Portfolio, User
from valutatrade_hub.core.utils import validate_amount, validate_currency_code
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

_USERS_FILE = "users.json"
_PORTFOLIOS_FILE = "portfolios.json"
_RATES_FILE = "rates.json"
_DEFAULT_BASE = "USD"


# ----- внутренние хелперы -----


def _read_users() -> list[dict]:
    return DatabaseManager().read(_USERS_FILE, default=[])


def _write_users(users: list[dict]) -> None:
    DatabaseManager().write(_USERS_FILE, users)


def _read_portfolios() -> list[dict]:
    return DatabaseManager().read(_PORTFOLIOS_FILE, default=[])


def _write_portfolios(portfolios: list[dict]) -> None:
    DatabaseManager().write(_PORTFOLIOS_FILE, portfolios)


def _find_portfolio_record(user_id: int) -> dict:
    record = next((p for p in _read_portfolios() if p.get("user_id") == user_id), None)
    if record is None:
        raise ValueError(f"Портфель пользователя id={user_id} не найден")
    return record


def _save_portfolio_record(record: dict) -> None:
    portfolios = _read_portfolios()
    for i, p in enumerate(portfolios):
        if p.get("user_id") == record["user_id"]:
            portfolios[i] = record
            _write_portfolios(portfolios)
            return
    portfolios.append(record)
    _write_portfolios(portfolios)


def _load_or_refresh_rates() -> dict[str, Any]:
    db = DatabaseManager()
    ttl = SettingsLoader().get("rates_ttl_seconds", 300)
    cached = db.read(_RATES_FILE, default=None)

    if cached is not None and "last_refresh" in cached:
        try:
            refreshed = datetime.fromisoformat(cached["last_refresh"])
            if refreshed.tzinfo is None:
                refreshed = refreshed.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - refreshed).total_seconds()
            if age <= ttl:
                return cached
        except ValueError:
            pass  # битая метка — считаем кеш устаревшим

    # Кеш пуст или устарел — обновляем из заглушки EXCHANGE_RATES.
    if not EXCHANGE_RATES:
        raise ApiRequestError("Курсы недоступны: заглушка пуста")

    now = datetime.now(UTC).isoformat()
    pairs = {
        key: {"rate": rate, "updated_at": now, "source": "stub"}
        for key, rate in EXCHANGE_RATES.items()
    }
    fresh = {"pairs": pairs, "last_refresh": now}
    db.write(_RATES_FILE, fresh)
    return fresh


def _flat_rates(rates_doc: dict[str, Any]) -> dict[str, float]:
    """Преобразовать формат 4.4 (pairs) в плоский dict для get_total_value."""
    pairs = rates_doc.get("pairs", {})
    return {key: pair["rate"] for key, pair in pairs.items()}


def _get_rate_value(from_code: str, to_code: str) -> tuple[float, str]:
    """Курс from→to и метка времени.

    rates.json хранит пары X_USD. Конвертация через USD.
    """
    doc = _load_or_refresh_rates()
    pairs = doc.get("pairs", {})

    def _usd(code: str) -> float | None:
        if code == _DEFAULT_BASE:
            return 1.0
        pair = pairs.get(f"{code}_{_DEFAULT_BASE}")
        return pair["rate"] if pair else None

    from_usd = _usd(from_code)
    to_usd = _usd(to_code)
    if from_usd is None or to_usd is None or to_usd == 0:
        raise CurrencyNotFoundError(f"Курс {from_code}→{to_code} недоступен")

    return from_usd / to_usd, doc.get("last_refresh", "")


# ----- пользователи -----


def register(username: str, password: str) -> User:
    """Зарегистрировать нового пользователя и создать пустой портфель.

    По ТЗ 2.2: username уникален и не пуст, пароль не короче 4 символов.
    """
    if not username:
        raise ValueError("Имя пользователя не может быть пустым")
    if len(password) < 4:
        raise ValueError("Пароль должен быть не короче 4 символов")

    users = _read_users()
    if any(u.get("username") == username for u in users):
        raise ValueError(f"Имя пользователя '{username}' уже занято")

    new_id = max((u.get("user_id", 0) for u in users), default=0) + 1
    user = User.create(user_id=new_id, username=username, password=password)

    users.append(user.to_dict())
    _write_users(users)

    portfolios = _read_portfolios()
    portfolios.append({"user_id": new_id, "wallets": {}})
    _write_portfolios(portfolios)

    return user


def login(username: str, password: str) -> User:
    """Проверить имя и пароль. Вернуть User или бросить ValueError"""
    users = _read_users()
    record = next((u for u in users if u.get("username") == username), None)
    if record is None:
        raise ValueError(f"Пользователь '{username}' не найден")

    user = User.from_dict(record)
    if not user.verify_password(password):
        raise ValueError("Неверный пароль")
    return user


# ----- портфель -----


def show_portfolio(
    user_id: int,
    username: str,
    base_currency: str = _DEFAULT_BASE,
) -> dict[str, Any]:
    """Собрать данные портфеля для печати (раздел 2.2).
    Печать — в CLI. Здесь только данные.
    """
    get_currency(base_currency)

    record = _find_portfolio_record(user_id)
    portfolio = Portfolio.from_dict(record)

    rates_doc = _load_or_refresh_rates()
    flat = _flat_rates(rates_doc)
    total = portfolio.get_total_value(base_currency=base_currency, rates=flat)

    wallets_info = []
    for code, wallet in portfolio.wallets.items():
        value = _convert(wallet.balance, code, base_currency, flat)
        wallets_info.append({"currency_code": code, "balance": wallet.balance, "value": value})

    return {
        "username": username,
        "base": base_currency.upper(),
        "wallets": wallets_info,
        "total": total,
    }


def _convert(amount: float, from_code: str, to_code: str, rates: dict[str, float]) -> float:
    """Конвертировать amount из from_code в to_code через USD."""

    def _usd(code: str) -> float | None:
        if code == _DEFAULT_BASE:
            return 1.0
        return rates.get(f"{code}_{_DEFAULT_BASE}")

    from_usd = _usd(from_code)
    to_usd = _usd(to_code)
    if from_usd is None or to_usd is None or to_usd == 0:
        raise CurrencyNotFoundError(f"Курс {from_code}→{to_code} недоступен")
    return amount * from_usd / to_usd


# ----- buy / sell -----


@log_action(action="BUY", verbose=True)
def buy(user_id: int, currency_code: str, amount: float) -> dict[str, Any]:
    """Купить валюту (упрощенная модель)
    Кошелек создаётся при отсутствии. USD не списываем.
    """
    code = validate_currency_code(currency_code)
    value = validate_amount(amount)
    get_currency(code)

    rate, _ = _get_rate_value(code, _DEFAULT_BASE)

    record = _find_portfolio_record(user_id)
    portfolio = Portfolio.from_dict(record)
    wallet = portfolio.add_currency(code)
    before = wallet.balance
    wallet.deposit(value)
    after = wallet.balance

    record = portfolio.to_dict()
    _save_portfolio_record(record)
    return {
        "currency_code": code,
        "amount": value,
        "rate": rate,
        "base": _DEFAULT_BASE,
        "before": before,
        "after": after,
        "estimated_value": value * rate,
    }


@log_action(action="SELL", verbose=True)
def sell(user_id: int, currency_code: str, amount: float) -> dict[str, Any]:
    """Продать валюту. Проверить кошелек и достаточность средств."""
    code = validate_currency_code(currency_code)
    value = validate_amount(amount)
    get_currency(code)

    rate, _ = _get_rate_value(code, _DEFAULT_BASE)

    record = _find_portfolio_record(user_id)
    portfolio = Portfolio.from_dict(record)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise InsufficientFundsError(
            f"У вас нет кошелька '{code}'. "
            "Добавьте валюту: она создаётся автоматически при первой покупке."
        )

    before = wallet.balance
    wallet.withdraw(value)
    after = wallet.balance

    _save_portfolio_record(portfolio.to_dict())
    return {
        "currency_code": code,
        "amount": value,
        "rate": rate,
        "base": _DEFAULT_BASE,
        "before": before,
        "after": after,
        "estimated_value": value * rate,
    }


def get_rate(from_code: str, to_code: str) -> dict[str, Any]:
    """Получить курс и обратный курс (ТЗ 2.2)."""
    from_norm = validate_currency_code(from_code)
    to_norm = validate_currency_code(to_code)

    rate, updated = _get_rate_value(from_norm, to_norm)
    reverse = 1.0 / rate if rate else 0.0

    return {
        "from_code": from_norm,
        "to_code": to_norm,
        "rate": rate,
        "reverse_rate": reverse,
        "updated_at": updated,
    }
