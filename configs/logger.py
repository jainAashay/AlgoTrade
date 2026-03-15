"""
Logging configuration module.
"""
import logging
from typing import Optional

from configs.config_loader import Config


def setup_logger(level: Optional[str] = None) -> None:
    """
    Set up logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If None, reads from config file.
    """
    if level is None:
        try:
            level_str = Config.get("logging", "level", default="INFO")
            level = getattr(logging, level_str.upper(), logging.INFO)
        except Exception:
            level = logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logger initialized with level: {logging.getLevelName(level)}")
