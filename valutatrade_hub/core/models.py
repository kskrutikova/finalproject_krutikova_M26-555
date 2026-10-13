"""Модели предметной области: User, Wallet, Portfolio."""

import hashlib
import secrets
from datetime import UTC, datetime

from valutatrade_hub.core.exceptions import (
    CurrencyNotFoundError,
    InsufficientFundsError,
)

# Фиксированные курсы-заглушка (ТЗ, раздел 2.1: «для упрощения можно задать
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
    """Пользователь системы.

    Атрибуты (приватные):
        _user_id: Уникальный идентификатор.
        _username: Имя пользователя.
        _hashed_password: Хеш пароля (SHA-256 с солью).
        _salt: Уникальная соль пользователя.
        _registration_date: Дата регистрации.
    """

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
        """Идентификатор пользователя."""
        return self._user_id

    @property
    def username(self) -> str:
        """Имя пользователя."""
        return self._username

    @username.setter
    def username(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value

    @property
    def salt(self) -> str:
        """Соль пользователя."""
        return self._salt

    @property
    def registration_date(self) -> datetime:
        """Дата регистрации."""
        return self._registration_date

    @staticmethod
    def _hash_password(password: str, salt: str) -> str:
        """Считает SHA-256 хеш от (password + salt)."""
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    def verify_password(self, password: str) -> bool:
        """Проверяет, совпадает ли пароль с сохранённым хешем."""
        return self._hash_password(password, self._salt) == self._hashed_password

    def change_password(self, new_password: str) -> None:
        """Меняет пароль, перегенерируя соль.

        Raises:
            ValueError: если пароль короче 4 символов.
        """
        if not isinstance(new_password, str) or len(new_password) < 4:
            raise ValueError("Пароль должен быть не короче 4 символов")
        self._salt = secrets.token_hex(8)
        self._hashed_password = self._hash_password(new_password, self._salt)

    def get_user_info(self) -> dict:
        """Возвращает информацию о пользователе без пароля и соли."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "registration_date": self._registration_date.isoformat(),
        }

    def to_dict(self) -> dict:
        """Сериализация в формат users.json (см. ТЗ, раздел 2.1)."""
        return {
            "user_id": self._user_id,
            "username": self._username,
            "hashed_password": self._hashed_password,
            "salt": self._salt,
            "registration_date": self._registration_date.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        """Восстанавливает объект User из словаря users.json."""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            hashed_password=data["hashed_password"],
            salt=data["salt"],
            registration_date=datetime.fromisoformat(data["registration_date"]),
        )

    @classmethod
    def create(cls, user_id: int, username: str, password: str) -> "User":
        """Создать нового пользователя: сгенерировать соль и хеш пароля.

        По ТЗ 2.2: пароль не короче 4 символов, username не пуст.
        """
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
    """Кошелёк пользователя для одной конкретной валюты.

    Атрибуты:
        currency_code: Код валюты (например, "USD", "BTC").
        _balance: Баланс в данной валюте.
    """

    def __init__(self, currency_code: str, balance: float = 0.0) -> None:
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        self.currency_code: str = currency_code.strip().upper()
        self._balance: float = 0.0
        self.balance = balance  # через сеттер — для валидации

    @property
    def balance(self) -> float:
        """Текущий баланс кошелька."""
        return self._balance

    @balance.setter
    def balance(self, value: float) -> None:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("Баланс должен быть числом")
        if value < 0:
            raise ValueError("Баланс не может быть отрицательным")
        self._balance = float(value)

    def deposit(self, amount: float) -> None:
        """Пополняет баланс.

        Raises:
            ValueError: если amount не положительное число.
        """
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("'amount' должен быть числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        self._balance += float(amount)

    def withdraw(self, amount: float) -> None:
        """Снимает средства со счёта.

        Raises:
            ValueError: если amount не положительное число.
            InsufficientFundsError: если на балансе недостаточно средств.
        """
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("'amount' должен быть числом")
        if amount <= 0:
            raise ValueError("'amount' должен быть положительным числом")
        if amount > self._balance:
            raise InsufficientFundsError(
                f"Недостаточно средств: доступно {self._balance} "
                f"{self.currency_code}, требуется {amount} {self.currency_code}"
            )
        self._balance -= float(amount)

    def get_balance_info(self) -> str:
        """Строковое представление баланса."""
        return f"{self.currency_code}: {self._balance}"

    def to_dict(self) -> dict:
        """Сериализация для portfolios.json (см. ТЗ, раздел 2.1)."""
        return {"currency_code": self.currency_code, "balance": self._balance}

    @classmethod
    def from_dict(cls, data: dict) -> "Wallet":
        """Восстанавливает Wallet из словаря."""
        return cls(
            currency_code=data["currency_code"],
            balance=data["balance"],
        )


class Portfolio:
    """Набор кошельков одного пользователя.

    Атрибуты:
        _user_id: Идентификатор владельца.
        _wallets: Словарь кошельков {код: Wallet}.
        _user: Опциональная ссылка на объект User (без сеттера).
    """

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
        """Объект пользователя (только для чтения)."""
        return self._user

    @property
    def wallets(self) -> dict[str, Wallet]:
        """Копия словаря кошельков (только для чтения)."""
        return dict(self._wallets)

    @property
    def user_id(self) -> int:
        """Идентификатор владельца портфеля."""
        return self._user_id

    def add_currency(self, currency_code: str) -> Wallet:
        """Добавляет кошелёк, если его ещё нет.

        Returns:
            Существующий или только что созданный Wallet.
        """
        if not isinstance(currency_code, str) or not currency_code.strip():
            raise ValueError("Код валюты не может быть пустым")
        code = currency_code.strip().upper()
        if code not in self._wallets:
            self._wallets[code] = Wallet(currency_code=code)
        return self._wallets[code]

    def get_wallet(self, currency_code: str) -> Wallet | None:
        """Возвращает кошелёк по коду или None."""
        if not isinstance(currency_code, str):
            return None
        return self._wallets.get(currency_code.strip().upper())

    def get_total_value(
        self,
        base_currency: str = "USD",
        rates: dict[str, float] | None = None,
    ) -> float:
        """Общая стоимость портфеля в base_currency.

        Конвертация идёт через USD (пары вида <CODE>_USD).
        Если rates не передан — используется фиксированный EXCHANGE_RATES.

        Args:
            base_currency: Код базовой валюты (по умолчанию "USD").
            rates: Словарь курсов вида {"BTC_USD": 59337.21, ...}.

        Raises:
            CurrencyNotFoundError: если для какой-то валюты нет курса
                к USD (или базовой валюте).
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
        """Сериализация для portfolios.json (см. ТЗ, раздел 2.1)."""
        return {
            "user_id": self._user_id,
            "wallets": {code: w.to_dict() for code, w in self._wallets.items()},
        }

    @classmethod
    def from_dict(cls, data: dict, user: User | None = None) -> "Portfolio":
        """Восстанавливает Portfolio из словаря."""
        wallets = {
            code: Wallet.from_dict(w_data) for code, w_data in data.get("wallets", {}).items()
        }
        return cls(user_id=data["user_id"], wallets=wallets, user=user)
