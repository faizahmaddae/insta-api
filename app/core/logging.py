"""
Logging configuration for the application.
Provides structured logging with different levels for development and production.
"""

import logging
import sys
from typing import Optional

from app.core.config import get_settings


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Configure and return the application logger.
    
    Args:
        level: Optional logging level override
        
    Returns:
        Configured logger instance
    """
    settings = get_settings()
    
    # Determine log level
    if level:
        log_level = getattr(logging, level.upper(), logging.INFO)
    elif settings.debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    
    # Create application logger
    logger = logging.getLogger("instaloader_api")
    logger.setLevel(log_level)
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    logger.info(f"Logging initialized at {logging.getLevelName(log_level)} level")
    
    return logger


# Create default logger instance
logger = setup_logging()
