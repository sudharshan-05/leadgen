"""
workers/self_healing.py - Autonomous Self-Healing Engine.
Monitors system state, restarts stuck jobs, and runs housekeeping routines.
"""
from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timedelta
from sqlalchemy import text

import config
import database
from workers.celery_app import app as celery_app
from workers.tasks import run_lead_pipeline_task
from monitoring import setup_logging, init_sentry

logger = setup_logging("self_healing_agent")
init_sentry("self_healing_agent")

def check_worker_health() -> bool:
    """Verify Celery workers status using control ping."""
    try:
        inspect = celery_app.control.inspect()
        pings = inspect.ping() if inspect else None
        if not pings:
            logger.error("HEALING WATCHDOG: No active Celery workers detected!")
            return False
        logger.info(f"HEALING WATCHDOG: Active Celery workers found: {list(pings.keys())}")
        return True
    except Exception as e:
        logger.error(f"HEALING WATCHDOG: Worker health inspection failed: {e}")
        return False

def check_database_health() -> bool:
    """Verify PostgreSQL database connectivity."""
    try:
        with database.get_db() as session:
            session.execute(text("SELECT 1"))
        logger.info("HEALING WATCHDOG: PostgreSQL database connection OK.")
        return True
    except Exception as e:
        logger.critical(f"HEALING WATCHDOG: Database health check failed: {e}")
        return False

def restart_stuck_jobs(timeout_minutes: int = 30) -> None:
    """Mark running jobs as failed if they have been running past the timeout threshold."""
    logger.info("HEALING ENGINE: Scanning for stuck jobs...")
    stuck_jobs = database.get_stuck_jobs(timeout_minutes=timeout_minutes)
    if not stuck_jobs:
        logger.info("HEALING ENGINE: No stuck jobs found.")
        return
        
    for job in stuck_jobs:
        logger.warning(f"HEALING ENGINE: Job {job.job_id} ({job.industry} in {job.location}) has been running since {job.started_at}. Restarting/Failing...")
        # Mark as failed to trigger retry mechanism
        database.update_job_status(
            job.job_id,
            status="failed",
            error_message=f"Job marked stuck after exceeding {timeout_minutes} minutes.",
            finished=True
        )

def retry_failed_jobs(max_retries: int = 3) -> None:
    """Scan database for failed jobs and trigger a retry if within limits."""
    logger.info("HEALING ENGINE: Scanning for failed jobs to retry...")
    failed_jobs = database.get_failed_retryable_jobs(max_retries=max_retries)
    if not failed_jobs:
        logger.info("HEALING ENGINE: No failed retryable jobs found.")
        return
        
    for job in failed_jobs:
        logger.info(f"HEALING ENGINE: Retrying failed job {job.job_id} (Attempt {job.retry_count + 1}/{max_retries})")
        # Increment retry count in database
        database.update_job_status(job.job_id, status="pending", inc_retry=True)
        # Re-dispatch Celery task
        run_lead_pipeline_task.delay(
            job_id=job.job_id,
            industry=job.industry,
            location=job.location,
            limit=job.limit,
            query_text=job.filters or "",
            telegram_chat_id=job.telegram_chat_id,
            user_id=job.user_id
        )

def cleanup_temp_files(max_age_days: int = 7) -> None:
    """Removes generated spreadsheets that have exceeded retention age."""
    logger.info("HEALING ENGINE: Cleaning up temporary export files...")
    try:
        folder = config.OUTPUTS_FOLDER
        now = time.time()
        removed_count = 0
        for filename in os.listdir(folder):
            if filename.endswith(".xlsx"):
                filepath = folder / filename
                if filepath.is_file():
                    stat = filepath.stat()
                    age_days = (now - stat.st_mtime) / (24 * 3600)
                    if age_days > max_age_days:
                        os.remove(filepath)
                        logger.info(f"HEALING ENGINE: Deleted old export file: {filename}")
                        removed_count += 1
        logger.info(f"HEALING ENGINE: Cleanup complete. Removed {removed_count} files.")
    except Exception as e:
        logger.error(f"HEALING ENGINE: Temp files cleanup crashed: {e}")

def run_watchdog_loop(interval_seconds: int = 60) -> None:
    """Main execution loop for self-healing operations."""
    logger.info(f"HEALING ENGINE: Startup complete. Running loops every {interval_seconds} seconds.")
    while True:
        try:
            check_database_health()
            check_worker_health()
            restart_stuck_jobs(timeout_minutes=30)
            retry_failed_jobs(max_retries=3)
            cleanup_temp_files(max_age_days=7)
        except Exception as e:
            logger.error(f"HEALING ENGINE: Watchdog loop encountered error: {e}")
            
        time.sleep(interval_seconds)

if __name__ == "__main__":
    # Start the self-healing daemon
    run_watchdog_loop()
