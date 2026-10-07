"""Small standard-library logging configuration for the application."""

import logging


LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def configure_logging(level: str = "INFO") -> None:
    normalized_level = level.strip().upper()
    if normalized_level not in VALID_LOG_LEVELS:
        choices = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ValueError(f"LOG_LEVEL must be one of: {choices}.")

    numeric_level = logging.getLevelName(normalized_level)
    logging.basicConfig(
        level=numeric_level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
    )
    # basicConfig is intentionally a no-op when Uvicorn has already installed
    # handlers; still apply the configured threshold to the root logger.
    logging.getLogger().setLevel(numeric_level)
