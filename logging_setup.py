"""Shared logging configuration: full log to pawpal.log, warnings to the console."""

from __future__ import annotations

import logging

LOG_FILE = "pawpal.log"


def setup_logging(log_file: str = LOG_FILE) -> logging.Logger:
    """Configure and return the 'pawpal' logger. Safe to call more than once."""
    logger = logging.getLogger("pawpal")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(file_handler)
    logger.addHandler(console)
    return logger
