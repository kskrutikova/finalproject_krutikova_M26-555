"""Пользовательские (доменные) исключения ValutaTrade Hub."""


class InsufficientFundsError(Exception):
    """Недостаточно средств на кошельке для выполнения операции."""


class CurrencyNotFoundError(Exception):
    """Валюта не найдена в реестре или отсутствует курс для конвертации."""


class ApiRequestError(Exception):
    """Ошибка при обращении к внешнему API (Parser Service)."""
