"""
workers/celery_app.py - Celery application initializer.
"""
from __future__ import annotations

import logging
from celery import Celery
import config
from monitoring import setup_logging, init_sentry

# Initialize logging and Sentry for celery
logger = setup_logging("celery_system")
init_sentry("celery_worker")

# Define celery app
app = Celery(
    "lead_tasks",
    broker=config.REDIS_URL,
    backend=config.REDIS_URL,
    include=["workers.tasks"]
)

# Celery configurations
app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes hard timeout
    task_soft_time_limit=25 * 60, # 25 minutes soft timeout
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1 # Single-task prefetching for Playwright workers
)

if __name__ == "__main__":
    app.start()
