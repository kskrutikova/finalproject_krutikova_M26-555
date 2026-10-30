"""Настройка логирования: формат, уровень, ротация файлов (п. 3.4)."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

# Имена логгеров: доменные операции и журнал Parser Service.
LOGGER_NAME = "valutatrade_hub.actions"
PARSER_LOGGER_NAME = "valutatrade_hub.parser"

_LOG_FORMAT = "%(levelname)s %(asctime)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_MAX_BYTES = 1_000_000  # 1 МБ
_BACKUP_COUNT = 3
_DEFAULT_LEVEL = "INFO"


def _resolve_level() -> int:
    """Возвращает уровень логов из конфигурации (п. 3.4: по умолчанию INFO)."""
    level_name = str(SettingsLoader().get("log_level", _DEFAULT_LEVEL)).upper()
    return getattr(logging, level_name, logging.INFO)


def _setup_logger(logger_name: str, filename: str) -> logging.Logger:
    """Настраивает логгер с текстовым форматом и ротацией файла в log_dir."""
    logger = logging.getLogger(logger_name)
    logger.setLevel(_resolve_level())
    logger.propagate = False

    # Идемпотентность: если handler уже добавлен - не дублируем.
    if logger.handlers:
        return logger

    log_dir = SettingsLoader().get("log_dir", "logs")
    project_root = Path(__file__).resolve().parents[1]
    log_path = project_root / log_dir / filename
    log_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    logger.addHandler(handler)

    return logger


def setup_logging() -> logging.Logger:
    """Возвращает логгер доменных операций logs/actions.log с ротацией."""
    return _setup_logger(LOGGER_NAME, "actions.log")


def setup_parser_logging() -> logging.Logger:
    """Возвращает логгер Parser Service logs/parser.log с ротацией."""
    return _setup_logger(PARSER_LOGGER_NAME, "parser.log")
