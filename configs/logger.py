"""
Logging configuration module.
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from configs.config_loader import Config


def setup_logger(level: Optional[str] = None) -> None:
    """
    Set up logging configuration with file rotation.

    Logs are written to a configurable directory (default: ``logs``)
    inside the container so it can be volume‑mounted from the host.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If None, reads from config file.
    """
    # Determine log level
    if level is None:
        try:
            level_str = Config.get("logging", "level", default="INFO")
            level = getattr(logging, level_str.upper(), logging.INFO)
        except Exception:
            level = logging.INFO

    # Determine log directory and file name (can be overridden in config)
    try:
        log_dir = Config.get("logging", "dir", default="logs")
    except Exception:
        log_dir = "logs"

    try:
        log_filename = Config.get("logging", "filename", default="app.log")
    except Exception:
        log_filename = "app.log"

    # Ensure directory exists
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_filename)

    # Optional rotation settings from config, with safe fallbacks
    try:
        max_bytes = int(Config.get("logging", "max_bytes", default=5 * 1024 * 1024))
    except Exception:
        max_bytes = 5 * 1024 * 1024

    try:
        backup_count = int(Config.get("logging", "backup_count", default=5))
    except Exception:
        backup_count = 5

    # Common formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Configure root logger explicitly (instead of basicConfig, for rotation)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if setup_logger is called more than once
    if root_logger.handlers:
        return

    # Rotating file handler (goes to volume‑mountable directory)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Stream handler to stdout (useful for `docker logs`)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    logger = logging.getLogger(__name__)
    logger.info(
        "Logger initialized with level=%s, file=%s, max_bytes=%s, backup_count=%s",
        logging.getLevelName(level),
        log_path,
        max_bytes,
        backup_count,
    )
