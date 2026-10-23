"""CLI: команды и сессия (ТЗ, п. 2.2, 3.6)"""

from __future__ import annotations

import shlex

from valutatrade_hub.core import usecases
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)

# current_user — сессия. Область видимости — модуль, потому что
# функции-команды вызываются диспетчером и должны видеть сессию.
_current_user = None


def _print_help() -> None:
    print("Доступные команды:")
    print("  register --username <name> --password <pw>")
    print("  login --username <name> --password <pw>")
    print("  show-portfolio [--base <code>]")
    print("  buy --currency <code> --amount <number>")
    print("  sell --currency <code> --amount <number>")
    print("  get-rate --from <code> --to <code>")
    print("  help")
    print("  exit / quit")


def _parse_flags(args: list[str]) -> dict[str, str]:
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
    return f"{value:.4f}"


def _fmt_usd(value: float) -> str:
    return f"{value:,.2f}"


def _fmt_rate_auto(value: float) -> str:
    if value < 1:
        return f"{value:.8f}"
    return f"{value:.2f}"


def _cmd_register(args: list[str]) -> None:
    global _current_user
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
        print("(пусто)")
    for w in data["wallets"]:
        print(
            f"- {w['currency_code']}: {_fmt_balance(w['balance'])}  "
            f"→ {_fmt_usd(w['value'])} {data['base']}"
        )
    print("-" * 33)
    print(f"ИТОГО: {_fmt_usd(data['total'])} {data['base']}")


def _cmd_buy(args: list[str]) -> None:
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


def _dispatch(command: str, args: list[str]) -> bool:
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

    print(f"Неизвестная команда: '{command}'. Введите 'help'.")
    return True


def run() -> None:
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
        except Exception as exc:  # noqa: BLE001
            # Точечная обработка — в блоках 2 и 3. Здесь — общий предохранитель.
            print(f"Ошибка: {exc}")
