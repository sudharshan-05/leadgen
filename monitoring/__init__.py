"""
monitoring package initializer.
"""
from __future__ import annotations

from monitoring.logger import setup_logging
from monitoring.sentry import init_sentry

__all__ = ["setup_logging", "init_sentry"]
