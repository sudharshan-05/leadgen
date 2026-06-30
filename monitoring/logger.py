"""
monitoring/logger.py - Centralized rotating logging configuration.
"""
from __future__ import annotations

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

import config

def setup_logging(service_name: str = "platform") -> logging.Logger:
    """Configures centralized logging with console outputs and rotating log files."""
    log_dir = config.LOG_FOLDER
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_path = log_dir / f"{service_name}.log"
    
    # Configure root logger
    root_logger = logging.getLogger()
    
    # Avoid duplicate handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.setLevel(logging.INFO if not getattr(config, "DEBUG", False) else logging.DEBUG)
    
    # Formatters
    log_format = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d) - %(message)s"
    formatter = logging.Formatter(log_format)
    
    # Rotating File Handler
    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=10 * 1024 * 1024, # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    
    # Windows-safe console stream handler
    console_stream = sys.stdout
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
            
    try:
        console_handler = logging.StreamHandler(console_stream)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
    except Exception:
        pass
        
    logger = logging.getLogger(service_name)
    logger.info(f"Logging configured for service: {service_name}. Logs saved to {log_path}")
    
    return logger
