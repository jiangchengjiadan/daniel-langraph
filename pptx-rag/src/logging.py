# src/logging.py
"""Logging configuration for PPTx RAG"""

import sys
from pathlib import Path
from loguru import logger
from .config import config


def setup_logging():
    """Configure logging with loguru"""
    # Remove default handler
    logger.remove()

    # Add console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{module}</cyan> | "
        "<level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    # Add file handler
    log_file = config.logs_dir / "app.log"
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module} | {message}",
        level="DEBUG",
        rotation="10 MB",
        retention="7 days",
        compression="gz",
    )

    return logger


# Initialize logging
log = setup_logging()
