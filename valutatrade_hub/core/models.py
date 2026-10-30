"""Модели предметной области: User, Wallet, Portfolio."""

import hashlib
import secrets
from datetime import UTC, datetime

from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
)

# Фиксированные курсы-заглушка (раздел 2.1: «для упрощения можно задать
# фиксированные курсы в словаре exchange_rates»). Ключ — пара <CODE>_USD.
# Используется методом Portfolio.get_total_value(), если rates не передан.
EXCHANGE_RATES: dict[str, float] = {
    "BTC_USD": 59337.21,
    "ETH_USD": 3720.00,
    "SOL_USD": 145.12,
    "EUR_USD": 1.0786,
    "GBP_USD": 1.2350,
    "RUB_USD": 0.01016,
}


class User:
    """Пользователь системы: имя, хеш пароля с солью и дата регистрации."""

    def __init__(
        self,
        user_id: int,
        username: str,
        hashed_password: str,
        salt: str,
        registration_date: datetime,
    ) -> None:
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._user_id: int = user_id
        self._username: str = username
        self._hashed_password: str = hashed_password
        self._salt: str = salt
        self._registration_date: datetime = registration_date

    @property
    def user_id(self) -> int:
        """Возвращает уникальный идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Возвращает имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        """Устанавливает имя пользователя, запрещая пустое значение."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value

    @property
    def salt(self) -> str:
        """Возвращает соль, использованную при хешировании пароля."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Возвращает дату регистрации пользователя."""
        return self._registration_date

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Возвращает SHA-256 хеш от строки password + salt."""
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли введенный пароль с сохраненным хешем."""
        return self._hash_password(password, self._salt) == self._hashed_password

    def change_password(self, new_password: str) -> None:
        """Заменяет пароль: генерирует новую соль и хранит только новый хеш."""
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = secrets.token_hex(8)
        self._hashed_password = self._hash_password(new_password, self._salt)

    def get_user_info(self) -> dict:
        """Возвращает публичную информацию о пользователе (без пароля)."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def to_dict(self) -> dict:
        """Сериализует пользователя в запись для data/users.json."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Восстанавливает пользователя из записи data/users.json."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> "User":
        """Создает нового пользователя: генерирует соль и хеширует пароль."""
        if not isinstance(password, str) or len(password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        salt = secrets.token_hex(8)
        hashed = cls._hash_password(password, salt)
        return cls(
            user_id=user_id,
            username=username,
            hashed_password=hashed,
            salt=salt,
            registration_date=datetime.now(UTC),
        )


class Wallet:
    """Кошелек пользователя под одну конкретную валюту."""

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        self.currency_code: str = currency_code.strip().upper()
        self._balance: float = 0.0
        self.balance = balance  # через сеттер — для валидации

    @property
    def balance(self) -> float:
        """Возвращает текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        """Устанавливает баланс, запрещая отрицательные и нечисловые значения."""
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополняет кошелек на положительную сумму amount."""
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("'amount' должен быть числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        self._balance += float(amount)

    def withdraw(self, amount: float) -> None:
        """Снимает amount, если баланса достаточно, иначе бросает InsufficientFundsError."""
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("'amount' должен быть числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        if amount > self._balance:
            raise InsufficientFundsError(
                f"Недостаточно средств: доступно {self._balance:.4f} "
                f"{self.currency_code}, требуется {amount:.4f} {self.currency_code}"
            )
        self._balance -= float(amount)

    def get_balance_info(self) -> str:
        """Возвращает человекочитаемую строку с балансом кошелька."""
        return f"{self.currency_code}: {self._balance}"

    def to_dict(self) -> dict:
        """Сериализует кошелек в запись для блока wallets в data/portfolios.json."""
        return {"currency_code": self.currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict) -> "Wallet":
        """Восстанавливает кошелек из записи портфеля."""
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"],
        )


class Portfolio:
    """Управляет всеми кошельками одного пользователя."""

    def __init__(
        self,
        user_id: int,
        wallets: dict[str, Wallet] | None = None,
        user: User | None = None,
    ) -> None:
        self._user_id: int = user_id
        self._wallets: dict[str, Wallet] = dict(wallets) if wallets else {}
        self._user: User | None = user

    @property
    def user(self) -> User | None:
        """Возвращает объект пользователя портфеля (только чтение)."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Возвращает копию словаря кошельков, чтобы словарь модели не мутировали извне."""
        return dict(self._wallets)

    @property
    def user_id(self) -> int:
        """Возвращает идентификатор владельца портфеля."""
        return self._user_id

    def add_currency(self, currency_code: str) -> Wallet:
        """Создает кошелек валюты, если его еще нет, и возвращает существующий или новый."""
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        code = currency_code.strip().upper()
        if code not in self._wallets:
            self._wallets[code] = Wallet(currency_code=code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Возвращает кошелек валюты или None, если такого кошелька нет."""
        if not isinstance(currency_code, str):
            return None
        return self._wallets.get(currency_code.strip().upper())

    def get_total_value(
        self,
        base_currency: str = "USD",
        rates: dict[str, float] | None = None,
    ) -> float:
        """Возвращает суммарную стоимость кошельков в base_currency.

        Курсы берутся из rates (пары вида X_USD); если rates не передан —
        из фиксированной заглушки EXCHANGE_RATES. Конвертация идет через USD:
        стоимость = balance * X_USD / BASE_USD.
        """
        effective_rates = rates if rates is not None else EXCHANGE_RATES
        base = base_currency.strip().upper()

        # Курс базовой валюты к USD.
        if base == "USD":
            base_to_usd = 1.0
        else:
            base_key = f"{base}_USD"
            if base_key not in effective_rates:
                raise CurrencyNotFoundError(f"Нет курса для базовой валюты '{base}'")
            base_to_usd = float(effective_rates[base_key])
            if base_to_usd == 0:
                raise CurrencyNotFoundError(f"Некорректный курс для базовой валюты '{base}'")

        total = 0.0
        for code, wallet in self._wallets.items():
            if code == "USD":
                value_in_usd = wallet.balance
            else:
                key = f"{code}_USD"
                if key not in effective_rates:
                    raise CurrencyNotFoundError(f"Нет курса для валюты '{code}' к USD")
                value_in_usd = wallet.balance * float(effective_rates[key])
            total += value_in_usd / base_to_usd
        return total

    def to_dict(self) -> dict:
        """Сериализует портфель в запись для data/portfolios.json."""
        return {
            "user_id": self._user_id,
            "wallets": {code: w.to_dict() for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict, user: User | None = None) -> "Portfolio":
        """Восстанавливает портфель из записи data/portfolios.json."""
        wallets = {
            code: Wallet.from_dict(w_data) for code, w_data in data.get("wallets", {}).items()
        }
        return cls(user_id=data["user_id"], wallets=wallets, user=user)
