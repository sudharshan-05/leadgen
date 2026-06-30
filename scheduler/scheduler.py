"""
scheduler/scheduler.py - Campaign Scheduler.
Queries active campaigns from PostgreSQL, schedules jobs using APScheduler,
and delegates execution to Celery background task workers.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import text

import config
import database
from database import get_db, Campaign, Job
from workers.tasks import run_lead_pipeline_task
from monitoring import setup_logging, init_sentry

logger = setup_logging("campaign_scheduler")
init_sentry("campaign_scheduler")

def calculate_next_run(frequency: str, run_time_str: str = "08:00", day_of_week_str: str | None = None) -> datetime:
    """Calculate the next execution timestamp based on campaign frequency and rules."""
    now = datetime.utcnow()
    
    try:
        hour, minute = map(int, run_time_str.split(":"))
    except ValueError:
        hour, minute = 8, 0
        
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if frequency == "daily":
        if next_run <= now:
            next_run += timedelta(days=1)
    elif frequency == "weekly":
        target_day = 0  # Monday
        days_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        if day_of_week_str and day_of_week_str.lower() in days_map:
            target_day = days_map[day_of_week_str.lower()]
            
        days_ahead = target_day - next_run.weekday()
        if days_ahead < 0 or (days_ahead == 0 and next_run <= now):
            days_ahead += 7
        next_run += timedelta(days=days_ahead)
    elif frequency == "monthly":
        if next_run <= now:
            next_run += timedelta(days=30)
            
    return next_run

def poll_and_dispatch_campaigns() -> None:
    """Watchdog checker: finds campaigns due for execution, creates jobs and enqueues Celery tasks."""
    logger.info("Scheduler poll starting...")
    now = datetime.utcnow()
    
    try:
        with get_db() as session:
            # Query campaigns where status is active and next_run is due
            due_campaigns = session.query(Campaign).filter(
                Campaign.status == "active",
                (Campaign.next_run <= now) | (Campaign.next_run.is_(None))
            ).all()
            
            if not due_campaigns:
                logger.info("No campaign runs are currently due.")
                return
                
            for campaign in due_campaigns:
                logger.info(f"Dispatching due campaign: {campaign.name} (ID: {campaign.id})")
                
                # Generate tracking Job details
                job_id = str(uuid.uuid4())
                
                # Create job record
                job = Job(
                    job_id=job_id,
                    status="pending",
                    retry_count=0,
                    started_at=datetime.utcnow(),
                    industry=campaign.industry,
                    location=campaign.location,
                    limit=campaign.count,
                    filters="",
                    telegram_chat_id=campaign.telegram_chat_id,
                    user_id=None
                )
                session.add(job)
                
                # Update Campaign timestamps
                next_exec = calculate_next_run(
                    frequency=campaign.frequency,
                    run_time_str=campaign.run_time,
                    day_of_week_str=campaign.day_of_week
                )
                campaign.last_run = now
                campaign.next_run = next_exec
                
                # Dispatch Celery Task
                run_lead_pipeline_task.apply_async(
                    args=[job_id, campaign.industry, campaign.location, campaign.count, ""],
                    kwargs={
                        "telegram_chat_id": campaign.telegram_chat_id,
                        "user_id": None
                    },
                    task_id=job_id
                )
                
                logger.info(f"Dispatched Celery task for campaign ID {campaign.id} to job ID {job_id}. Next execution set to: {next_exec}")
                
            session.commit()
            
    except Exception as e:
        logger.error(f"Error checking campaigns dispatch queue: {e}")

def run_scheduler() -> None:
    """Initialize APScheduler loop and run watchdog checks."""
    scheduler = BlockingScheduler()
    
    # Run poll every 60 seconds to dispatch jobs
    scheduler.add_job(poll_and_dispatch_campaigns, "interval", seconds=60, id="campaign_poll")
    
    # Dispatch immediately on startup
    scheduler.add_job(poll_and_dispatch_campaigns, "date", run_date=datetime.now() + timedelta(seconds=5))
    
    logger.info("APScheduler initialized. Starting BlockingScheduler loops...")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shutting down gracefully.")

if __name__ == "__main__":
    run_scheduler()
