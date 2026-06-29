import logging
import sys

from app.config import settings

_SECRET_VALUES = [
    settings.META_ACCESS_TOKEN,
    settings.META_APP_SECRET,
    settings.GROQ_API_KEY,
    settings.ADMIN_API_KEY,
]


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in _SECRET_VALUES:
            if secret and len(secret) >= 6 and secret in message:
                message = message.replace(secret, "***REDACTED***")
        record.msg = message
        record.args = ()
        return True


def configure_logging() -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.upper())

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RedactSecretsFilter())

    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
