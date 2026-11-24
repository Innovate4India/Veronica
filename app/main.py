"""Application entry point for the Phase 1 scaffold."""

from app.core.logger import get_logger


def main() -> int:
    logger = get_logger()
    logger.info("Veronica Phase 1 started successfully.")
    return 0
