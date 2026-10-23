"""Настройка логирования (п. 3.4)"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

# Имя логгера, которое будут использовать декоратор и usecases.
LOGGER_NAME = "valutatrade_hub.actions"

_LOG_FORMAT = "%(levelname)s %(asctime)s %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_MAX_BYTES = 1_000_000  # 1 МБ
_BACKUP_COUNT = 3


def setup_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Идемпотентность: если handler уже добавлен - не дублируем.
    if logger.handlers:
        return logger

    log_dir = SettingsLoader().get("log_dir", "logs")
    project_root = Path(__file__).resolve().parents[1]
    log_path = project_root / log_dir / "actions.log"
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


PARSER_LOGGER_NAME = "valutatrade_hub.parser"


def setup_parser_logging() -> logging.Logger:
    logger = logging.getLogger(PARSER_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    log_dir = SettingsLoader().get("log_dir", "logs")
    project_root = Path(__file__).resolve().parents[1]
    log_path = project_root / log_dir / "parser.log"
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
