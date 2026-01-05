"""Logging configuration for CHIMERA."""

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from chimera.config import DEFAULT_CONFIG_DIR


def setup_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    console: bool = True,
) -> logging.Logger:
    """Set up logging for CHIMERA.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files (defaults to ~/.chimera/logs)
        console: Whether to log to console
        
    Returns:
        Configured logger
    """
    if log_dir is None:
        log_dir = DEFAULT_CONFIG_DIR / "logs"
    
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("chimera")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler with rich formatting
    if console:
        console_handler = RichHandler(
            console=Console(stderr=True),
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
        )
        console_handler.setLevel(logging.DEBUG)
        logger.addHandler(console_handler)
    
    # File handlers
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Main log file
    main_handler = logging.FileHandler(log_dir / "chimerad.log")
    main_handler.setLevel(logging.INFO)
    main_handler.setFormatter(formatter)
    logger.addHandler(main_handler)
    
    # Error log file
    error_handler = logging.FileHandler(log_dir / "error.log")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    logger.addHandler(error_handler)
    
    return logger


def get_logger(name: str = "chimera") -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)
