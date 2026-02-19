from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from beru.utils.config import get_config


def setup_logging(name: str = "beru") -> logging.Logger:
    config = get_config()
    log_config = config.logging

    Path(log_config.file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_config.level.upper()))

    logger.handlers.clear()

    formatter = logging.Formatter(log_config.format)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_config.file,
        maxBytes=log_config.max_size_mb * 1024 * 1024,
        backupCount=log_config.backup_count,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def get_logger(name: str = "beru") -> logging.Logger:
    return logging.getLogger(name)


_root_logger: Optional[logging.Logger] = None


def init_logging() -> logging.Logger:
    global _root_logger
    if _root_logger is None:
        _root_logger = setup_logging("beru")
    return _root_logger
