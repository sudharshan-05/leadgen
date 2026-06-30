"""
monitoring/sentry.py - Sentry SDK integration wrapper.
"""
from __future__ import annotations

import logging
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastAPIIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

import config

logger = logging.getLogger(__name__)

def init_sentry(service_name: str = "platform") -> None:
    """Initialize Sentry SDK with standard integrations if DSN is set."""
    dsn = config.SENTRY_DSN
    if not dsn:
        logger.info("Sentry DSN is not set. Skipping error-reporting integration.")
        return
        
    sentry_logging = LoggingIntegration(
        level=logging.INFO,        # Capture info/warn/error breadcrumbs
        event_level=logging.ERROR   # Send errors as events
    )
    
    try:
        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                sentry_logging,
                CeleryIntegration(),
                FastAPIIntegration()
            ],
            traces_sample_rate=1.0 if getattr(config, "DEBUG", False) else 0.1,
            environment=config.ENV,
            release=f"lead-agent@{service_name}"
        )
        logger.info(f"Sentry SDK initialized successfully for: {service_name}")
    except Exception as e:
        logger.error(f"Failed to initialize Sentry SDK: {e}")
