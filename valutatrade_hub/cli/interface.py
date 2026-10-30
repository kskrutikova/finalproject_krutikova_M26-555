"""CLI: команды и сессия (ТЗ, п. 2.2, 3.6)"""

from __future__ import annotations

import shlex

from valutatrade_hub.core import usecases
from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.config import ParserConfig
from valutatrade_hub.parser_service.storage import RatesStorage
from valutatrade_hub.parser_service.updater import RatesUpdater

# current_user — сессия. Область видимости — модуль, потому что
# функции-команды вызываются диспетчером и должны видеть сессию.
_current_user = None


def _print_help() -> None:
    """Печатает список доступных команд."""
    print("Доступные команды:")
    print("  register --username <name> --password <pw>")
    print("  login --username <name> --password <pw>")
    print("  show-portfolio [--base <code>]")
    print("  buy --currency <code> --amount <number>")
    print("  sell --currency <code> --amount <number>")
    print("  get-rate --from <code> --to <code>")
    print("  update-rates [--source coingecko|exchangerate]")
    print("  show-rates [--currency CODE] [--top N] [--base CODE]")
    print("  help")
    print("  exit / quit")


def _parse_flags(args: list[str]) -> dict[str, str]:
    """Разбирает аргументы вида --key value в словарь {key: value}."""
    result: dict[str, str] = {}
    i = 0
    while i < len(args):
        token = args[i]
        if not token.startswith("--"):
            raise ValueError(f"Ожидался флаг, получено: '{token}'")
        key = token[2:]
        if i + 1 >= len(args):
            raise ValueError(f"У флага '--{key}' нет значения")
        result[key] = args[i + 1]
        i += 2
    return result


def _fmt_balance(value: float) -> str:
    """Форматирует баланс кошелька для таблицы портфеля."""
    return f"{value:.4f}"


def _fmt_usd(value: float) -> str:
    """Форматирует денежную сумму: разделители тысяч и два знака."""
    return f"{value:,.2f}"


def _fmt_rate_auto(value: float) -> str:
    """Форматирует курс: мелкие значения — с восемью знаками, крупные — с двумя."""
    if value < 1:
        return f"{value:.8f}"
    return f"{value:.2f}"


def _cmd_register(args: list[str]) -> None:
    """Команда register: создает пользователя (ТЗ 2.2, п. 1)."""
    flags = _parse_flags(args)
    username = flags.get("username")
    password = flags.get("password")
    if not username or not password:
        print("Использование: register --username <name> --password <pw>")
        return

    try:
        user = usecases.register(username, password)
    except ValueError as exc:
        print(exc)
        return

    print(
        f"Пользователь '{user.username}' зарегистрирован (id={user.user_id}). "
        f"Войдите: login --username {user.username} --password ****"
    )


def _cmd_login(args: list[str]) -> None:
    """Команда login: проверяет пароль и запоминает пользователя в сессии CLI."""
    global _current_user
    flags = _parse_flags(args)
    username = flags.get("username")
    password = flags.get("password")
    if not username or not password:
        print("Использование: login --username <name> --password <pw>")
        return

    try:
        user = usecases.login(username, password)
    except ValueError as exc:
        print(exc)
        return

    _current_user = user
    print(f"Вы вошли как '{user.username}'")


def _cmd_get_rate(args: list[str]) -> None:
    """Команда get-rate: курс одной валюты к другой и обратный курс (ТЗ 2.2, п. 6)."""
    flags = _parse_flags(args)
    from_code = flags.get("from")
    to_code = flags.get("to")
    if not from_code or not to_code:
        print("Использование: get-rate --from <code> --to <code>")
        return

    try:
        result = usecases.get_rate(from_code, to_code)
    except CurrencyNotFoundError as exc:
        print(exc)
        return
    except ApiRequestError as exc:
        print(exc)
        return

    print(
        f"Курс {result['from_code']}→{result['to_code']}: "
        f"{_fmt_rate_auto(result['rate'])} "
        f"(обновлено: {result['updated_at']})"
    )
    print(
        f"Обратный курс {result['to_code']}→{result['from_code']}: "
        f"{_fmt_rate_auto(result['reverse_rate'])}"
    )


def _cmd_show_portfolio(args: list[str]) -> None:
    """Команда show-portfolio: кошельки и итог в базовой валюте (ТЗ 2.2, п. 3)."""
    global _current_user
    if _current_user is None:
        print("Сначала выполните login")
        return

    flags = _parse_flags(args)
    base = flags.get("base", "USD")

    try:
        data = usecases.show_portfolio(
            _current_user.user_id, _current_user.username, base_currency=base
        )
    except CurrencyNotFoundError as exc:
        print(exc)
        return
    except ApiRequestError as exc:
        print(exc)
        return

    print(f"Портфель пользователя '{data['username']}' (база: {data['base']}):")

    if not data["wallets"]:
        print("Портфель пуст: кошельки появятся после первой покупки.")
        return

    for w in data["wallets"]:
        print(
            f"- {w['currency_code']}: {_fmt_balance(w['balance'])}  "
            f"→ {_fmt_usd(w['value'])} {data['base']}"
        )
    print("-" * 33)
    print(f"ИТОГО: {_fmt_usd(data['total'])} {data['base']}")


def _cmd_buy(args: list[str]) -> None:
    """Команда buy: покупка валюты залогиненным пользователем (ТЗ 2.2, п. 4)."""
    global _current_user
    if _current_user is None:
        print("Сначала выполните login")
        return

    flags = _parse_flags(args)
    currency = flags.get("currency")
    amount = flags.get("amount")
    if not currency or amount is None:
        print("Использование: buy --currency <code> --amount <number>")
        return

    try:
        result = usecases.buy(
            user_id=_current_user.user_id,
            currency_code=currency,
            amount=amount,
        )
    except ValueError as exc:
        print(exc)
        return
    except CurrencyNotFoundError as exc:
        print(exc)
        return
    except ApiRequestError as exc:
        print(exc)
        return

    print(
        f"Покупка выполнена: {_fmt_balance(result['amount'])} "
        f"{result['currency_code']} по курсу "
        f"{_fmt_rate_auto(result['rate'])} {result['base']}/{result['currency_code']}"
    )
    print("Изменения в портфеле:")
    print(
        f"- {result['currency_code']}: было {_fmt_balance(result['before'])} "
        f"→ стало {_fmt_balance(result['after'])}"
    )
    print(f"Оценочная стоимость покупки: {_fmt_usd(result['estimated_value'])} USD")


def _cmd_sell(args: list[str]) -> None:
    """Команда sell: продажа валюты с проверкой кошелька и средств (ТЗ 2.2, п. 5)."""
    global _current_user
    if _current_user is None:
        print("Сначала выполните login")
        return

    flags = _parse_flags(args)
    currency = flags.get("currency")
    amount = flags.get("amount")
    if not currency or amount is None:
        print("Использование: sell --currency <code> --amount <number>")
        return

    try:
        result = usecases.sell(
            user_id=_current_user.user_id,
            currency_code=currency,
            amount=amount,
        )
    except ValueError as exc:
        print(exc)
        return
    except InsufficientFundsError as exc:
        print(exc)
        return
    except CurrencyNotFoundError as exc:
        print(exc)
        return
    except ApiRequestError as exc:
        print(exc)
        return

    print(
        f"Продажа выполнена: {_fmt_balance(result['amount'])} "
        f"{result['currency_code']} по курсу "
        f"{_fmt_rate_auto(result['rate'])} {result['base']}/{result['currency_code']}"
    )
    print("Изменения в портфеле:")
    print(
        f"- {result['currency_code']}: было {_fmt_balance(result['before'])} "
        f"→ стало {_fmt_balance(result['after'])}"
    )
    print(f"Оценочная выручка: {_fmt_usd(result['estimated_value'])} USD")


def _cmd_update_rates(args: list[str]) -> None:
    """Команда update-rates: немедленное обновление курсов Parser Service (ТЗ 4.4)."""
    flags = _parse_flags(args)
    source = flags.get("source", "").lower()

    config = ParserConfig()
    storage = RatesStorage(config)

    clients = []
    if source in ("", "all"):
        clients = [CoinGeckoClient(config), ExchangeRateApiClient(config)]
    elif source == "coingecko":
        clients = [CoinGeckoClient(config)]
    elif source == "exchangerate":
        clients = [ExchangeRateApiClient(config)]
    else:
        print("Неизвестный источник. Доступны: coingecko, exchangerate.")
        return

    updater = RatesUpdater(config=config, clients=clients, storage=storage)

    print("INFO: Starting rates update...")

    try:
        updated_counts = updater.run_update()
    except ApiRequestError as exc:
        print(f"ERROR: {exc}")
        print("Update completed with errors. Check logs/parser.log for details.")
        return

    total = sum(updated_counts.values())

    if not total:
        print("Update completed with errors. Check logs/parser.log for details.")
        return

    print(f"Update successful. Total rates updated: {total}.")


def _cmd_show_rates(args: list[str]) -> None:
    """Команда show-rates: курсы из локального кеша с фильтрами (ТЗ 4.4)."""
    flags = _parse_flags(args)
    currency = flags.get("currency", "").upper()
    top_raw = flags.get("top")
    base = flags.get("base", "USD").upper()

    rates_doc = DatabaseManager().read("rates.json", default=None)

    if not rates_doc or not rates_doc.get("pairs"):
        print("Локальный кеш курсов пуст. Выполните 'update-rates', чтобы загрузить данные.")
        return

    pairs = rates_doc["pairs"]

    try:
        get_currency(base)
    except CurrencyNotFoundError as exc:
        print(exc)
        return

    base_rate = 1.0 if base == "USD" else pairs.get(f"{base}_USD", {}).get("rate")

    if base_rate is None or base_rate == 0:
        print(f"Курс для базовой валюты '{base}' не найден в кеше.")
        return

    filtered = []

    for pair, info in pairs.items():
        from_code, to_code = pair.split("_", 1)

        if currency and currency not in (from_code, to_code):
            continue

        rate = info["rate"]

        if base != "USD":
            rate = rate / base_rate

        filtered.append((pair, rate, info["updated_at"]))

    if not filtered:
        print(f"Курс для '{currency}' не найден в кеше.")
        return

    if top_raw is not None:
        try:
            top = int(top_raw)
        except ValueError:
            print("'top' должен быть целым числом")
            return

        filtered = sorted(filtered, key=lambda item: item[1], reverse=True)[:top]
    else:
        filtered.sort(key=lambda item: item[0])

    print(f"Rates from cache (updated at {rates_doc.get('last_refresh', '')}):")

    for pair, rate, _updated_at in filtered:
        print(f"- {pair}: {_fmt_rate_auto(rate)}")


def _dispatch(command: str, args: list[str]) -> bool:
    """Вызывает команду по имени. Возвращает False, если пользователь вышел."""
    if command in ("exit", "quit"):
        return False
    if command == "help":
        _print_help()
        return True

    if command == "register":
        _cmd_register(args)
        return True
    if command == "login":
        _cmd_login(args)
        return True
    if command == "get-rate":
        _cmd_get_rate(args)
        return True
    if command == "show-portfolio":
        _cmd_show_portfolio(args)
        return True
    if command == "buy":
        _cmd_buy(args)
        return True
    if command == "sell":
        _cmd_sell(args)
        return True
    if command == "update-rates":
        _cmd_update_rates(args)
        return True
    if command == "show-rates":
        _cmd_show_rates(args)
        return True

    print(f"Неизвестная команда: '{command}'. Введите 'help'.")
    return True


def run() -> None:
    """Главный цикл CLI: читает строки команд и передает их диспетчеру."""
    print("ValutaTrade Hub. Введите 'help' для списка команд.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        try:
            parts = shlex.split(line)
        except ValueError as exc:
            print(f"Ошибка разбора команды: {exc}")
            continue

        command = parts[0]
        args = parts[1:]

        try:
            if not _dispatch(command, args):
                break
        except Exception as exc:
            # Точечная обработка в блоках команд. Здесь общий предохранитель,
            # чтобы одна ошибка не роняла весь цикл.
            print(f"Ошибка: {exc}")
