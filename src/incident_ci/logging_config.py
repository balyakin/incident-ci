import logging
import sys

LOGGER_NAME = "incident_ci"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str) -> logging.Logger:
    """Configure application logging."""

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        stream=sys.stderr,
    )
    return logging.getLogger(LOGGER_NAME)
