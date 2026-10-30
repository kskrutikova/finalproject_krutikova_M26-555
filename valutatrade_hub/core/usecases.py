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
from valutatrade_hub.core.utils import utc_timestamp, validate_amount, validate_currency_code
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

# ----- внутренние хелперы хранилища -----

# Имена файлов хранилища (читаются/пишутся через DatabaseManager).
_USERS_FILE = "users.json"
_PORTFOLIOS_FILE = "portfolios.json"
_RATES_FILE = "rates.json"

# Значения по умолчанию, если ключа нет в [tool.valutatrade] (п. 3.3).
DEFAULT_BASE = SettingsLoader().get("default_base_currency", "USD")
_RATES_TTL_SECONDS = 300

# Базовая валюта пар в rates.json: Parser Service пишет курсы вида X_USD (ТЗ 4.4).
_RATES_BASE = "USD"

# Источник курсов, когда кеш заполнен фиктивной таблицей, а не Parser Service.
_STUB_SOURCE = "stub"


def _read_users() -> list[dict]:
    """Возвращает список записей пользователей из data/users.json."""
    return DatabaseManager().read(_USERS_FILE, default=[])


def _write_users(users: list[dict]) -> None:
    """Сохраняет список пользователей в data/users.json."""
    DatabaseManager().write(_USERS_FILE, users)


def _read_portfolios() -> list[dict]:
    """Возвращает список записей портфелей из data/portfolios.json."""
    return DatabaseManager().read(_PORTFOLIOS_FILE, default=[])


def _write_portfolios(portfolios: list[dict]) -> None:
    """Сохраняет список портфелей в data/portfolios.json."""
    DatabaseManager().write(_PORTFOLIOS_FILE, portfolios)


def _find_portfolio_record(user_id: int) -> dict:
    """Возвращает запись портфеля пользователя; если ее нет — бросает ValueError."""
    record = next((p for p in _read_portfolios() if p.get("user_id") == user_id), None)
    if record is None:
        raise ValueError(f"Портфель пользователя id={user_id} не найден")
    return record


def _save_portfolio_record(record: dict) -> None:
    """Обновляет запись портфеля в data/portfolios.json (или добавляет новую)."""
    portfolios = _read_portfolios()
    for i, p in enumerate(portfolios):
        if p.get("user_id") == record["user_id"]:
            portfolios[i] = record
            _write_portfolios(portfolios)
            return
    portfolios.append(record)
    _write_portfolios(portfolios)


def _stub_rates_doc() -> dict[str, Any]:
    """Возвращает снимок курсов из фиктивной таблицы EXCHANGE_RATES (ТЗ 2.2)."""
    if not EXCHANGE_RATES:
        raise ApiRequestError("Курсы недоступны: фиктивная таблица пуста")

    now = utc_timestamp()
    pairs = {
        key: {"rate": rate, "updated_at": now, "source": _STUB_SOURCE}
        for key, rate in EXCHANGE_RATES.items()
    }
    return {"pairs": pairs, "last_refresh": now}


def _cache_age_seconds(rates_doc: dict[str, Any]) -> float | None:
    """Возвращает возраст кеша в секундах; None, если метка времени не читается."""
    stamp = rates_doc.get("last_refresh")
    if not stamp:
        return None
    try:
        refreshed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if refreshed.tzinfo is None:
        refreshed = refreshed.replace(tzinfo=UTC)
    return (datetime.now(UTC) - refreshed).total_seconds()


def _load_rates() -> tuple[dict[str, Any], bool]:
    """Читает кеш курсов и проверяет его свежесть по TTL из SettingsLoader.

    Пустой кеш заполняется фиктивной таблицей (ТЗ 2.2). Устаревший кеш не
    перезаписывается: значения в нем мог сохранить Parser Service, поэтому
    курс возвращается как есть, а второй результат говорит «данные устарели»
    (ТЗ 4.4: Core честно сообщает об этом и предлагает обновить).
    """
    db = DatabaseManager()
    rates_doc = db.read(_RATES_FILE, default=None)

    if not rates_doc or not rates_doc.get("pairs"):
        fresh = _stub_rates_doc()
        db.write(_RATES_FILE, fresh)
        return fresh, False

    ttl = SettingsLoader().get("rates_ttl_seconds", _RATES_TTL_SECONDS)
    age = _cache_age_seconds(rates_doc)
    return rates_doc, age is None or age > ttl


def _flat_rates(rates_doc: dict[str, Any]) -> dict[str, float]:
    """Преобразовать формат 4.4 (pairs) в плоский dict для get_total_value."""
    pairs = rates_doc.get("pairs", {})
    return {key: pair["rate"] for key, pair in pairs.items()}


def _rate_to_usd(code: str, rates: dict[str, float]) -> float | None:
    """Возвращает курс валюты к базе кеша (USD) по парам X_USD; для самой базы это 1.0."""
    if code == _RATES_BASE:
        return 1.0
    return rates.get(f"{code}_{_RATES_BASE}")


def _convert(amount: float, from_code: str, to_code: str, rates: dict[str, float]) -> float:
    """Конвертировать amount из from_code в to_code через базовую валюту кеша."""
    from_usd = _rate_to_usd(from_code, rates)
    to_usd = _rate_to_usd(to_code, rates)
    if from_usd is None or to_usd is None or to_usd == 0:
        raise CurrencyNotFoundError(f"Курс {from_code}→{to_code} недоступен")
    return amount * from_usd / to_usd


def _get_rate_value(from_code: str, to_code: str) -> tuple[float, str, bool]:
    """Курс from→to, метка обновления кеша и признак того, что кеш устарел.

    ТЗ 2.2, п. 6 и ТЗ 4.4: устаревший кеш не затирается, а возвращается
    с предупреждением, чтобы Core не портил данные Parser Service.
    """
    doc, stale = _load_rates()
    rate = _convert(1.0, from_code, to_code, _flat_rates(doc))
    return rate, doc.get("last_refresh", ""), stale


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
    """Проверить имя и пароль. Вернуть User или бросить ValueError."""
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
    base_currency: str = DEFAULT_BASE,
) -> dict[str, Any]:
    """Собрать данные портфеля для печати (раздел 2.2).

    Печать — в CLI, здесь только данные.
    """
    get_currency(base_currency)

    record = _find_portfolio_record(user_id)
    portfolio = Portfolio.from_dict(record)

    rates_doc, stale = _load_rates()
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
        "stale": stale,
    }


# ----- buy / sell -----


@log_action(action="BUY", verbose=True)
def buy(user_id: int, currency_code: str, amount: float) -> dict[str, Any]:
    """Купить валюту (упрощенная модель, см. README).

    Кошелек создается при отсутствии, USD не списывается.
    """
    code = validate_currency_code(currency_code)
    value = validate_amount(amount)

    rate, _, stale = _get_rate_value(code, DEFAULT_BASE)

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
        "base": DEFAULT_BASE,
        "before": before,
        "after": after,
        "estimated_value": value * rate,
        "stale": stale,
    }


@log_action(action="SELL", verbose=True)
def sell(user_id: int, currency_code: str, amount: float) -> dict[str, Any]:
    """Продать валюту. Проверить кошелек и достаточность средств."""
    code = validate_currency_code(currency_code)
    value = validate_amount(amount)

    rate, _, stale = _get_rate_value(code, DEFAULT_BASE)

    record = _find_portfolio_record(user_id)
    portfolio = Portfolio.from_dict(record)
    wallet = portfolio.get_wallet(code)
    if wallet is None:
        raise InsufficientFundsError(
            f"У вас нет кошелька '{code}'. "
            "Добавьте валюту: она создается автоматически при первой покупке."
        )

    before = wallet.balance
    wallet.withdraw(value)
    after = wallet.balance

    _save_portfolio_record(portfolio.to_dict())
    return {
        "currency_code": code,
        "amount": value,
        "rate": rate,
        "base": DEFAULT_BASE,
        "before": before,
        "after": after,
        "estimated_value": value * rate,
        "stale": stale,
    }


def get_rate(from_code: str, to_code: str) -> dict[str, Any]:
    """Получить курс и обратный курс (ТЗ 2.2).

    Обратный курс считается из неокругленного прямого (ответ преподавателя №3).
    """
    from_norm = validate_currency_code(from_code)
    to_norm = validate_currency_code(to_code)

    rate, updated, stale = _get_rate_value(from_norm, to_norm)
    reverse = 1.0 / rate if rate else 0.0

    return {
        "from_code": from_norm,
        "to_code": to_norm,
        "rate": rate,
        "reverse_rate": reverse,
        "updated_at": updated,
        "stale": stale,
    }
