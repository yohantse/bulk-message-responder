import json
import logging
import sys
from typing import Any, ClassVar

from app.config.settings import get_settings


class StructuredJsonFormatter(logging.Formatter):
    """
    JSON formatter that masks sensitive fields (tokens, secrets, passwords).
    """

    SENSITIVE_KEYS: ClassVar[set[str]] = {
        "bot_token",
        "telegram_bot_token",
        "webhook_secret",
        "telegram_webhook_secret",
        "password",
        "secret",
        "database_url",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include structured extra fields if provided
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            for k, v in record.extra_fields.items():
                if any(sens in k.lower() for sens in self.SENSITIVE_KEYS):
                    log_data[k] = "******"
                else:
                    log_data[k] = v

        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging() -> None:
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(StructuredJsonFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
