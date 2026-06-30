"""
config/__init__.py - Unified environment settings loader.
Exposes settings parameters based on ENV flag.
"""
from __future__ import annotations

import logging
from config.settings import *
from config.settings import ENV

logger = logging.getLogger(__name__)

if ENV == "development":
    logger.info("Loading development configuration")
    from config.development import DATABASE_URL, REDIS_URL, DEBUG
else:
    logger.info("Loading production configuration")
    from config.production import DATABASE_URL, REDIS_URL, DEBUG

__all__ = [
    "ENV",
    "DATABASE_URL",
    "REDIS_URL",
    "DEBUG",
    "TELEGRAM_BOT_TOKEN",
    "SENTRY_DSN",
    "GOOGLE_MAPS_API_KEY",
    "OUTPUTS_FOLDER",
    "LOG_FOLDER",
    "MIN_SCORE_TO_QUALIFY",
    "HOT_SCORE_THRESHOLD",
    "WARM_SCORE_THRESHOLD",
    "REQUEST_DELAY_MIN",
    "REQUEST_DELAY_MAX",
    "WEBSITE_TIMEOUT",
    "MAX_RETRIES",
    "SCRAPER_WORKERS",
    "WEBSITE_ANALYSER_WORKERS",
    "USER_AGENTS",
    "INDUSTRY_KEYWORDS",
    "LOCATION_KEYWORDS"
]
