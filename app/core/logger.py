"""Standard-library logging configuration."""

import logging

from app.config import APP_NAME, LOG_DIR, LOG_FILE


def get_logger() -> logging.Logger:
    logger = logging.getLogger(APP_NAME)
    if not logger.handlers:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        logger.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
