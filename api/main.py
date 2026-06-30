"""
api/main.py - FastAPI health and system monitoring service.
"""
from __future__ import annotations

import logging
from fastapi import FastAPI, HTTPException
from sqlalchemy import text
import redis

import config
import database
from workers.celery_app import app as celery_app
from monitoring import setup_logging, init_sentry

# Initialize logging and Sentry
logger = setup_logging("monitoring_api")
init_sentry("monitoring_api")

app = FastAPI(
    title="Lead Intelligence Platform - Monitoring API",
    description="System health check, worker statuses, and campaign metrics endpoints.",
    version="1.0.0"
)

def check_db_health() -> bool:
    """Check database connection."""
    try:
        with database.get_db() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"API Health: Database connection failed: {e}")
        return False

def check_redis_health() -> bool:
    """Check Redis connection."""
    try:
        r = redis.from_url(config.REDIS_URL, socket_timeout=3)
        return r.ping()
    except Exception as e:
        logger.error(f"API Health: Redis connection failed: {e}")
        return False

def check_celery_workers() -> list[str]:
    """Inspect and return active Celery worker names."""
    try:
        inspect = celery_app.control.inspect()
        pings = inspect.ping() if inspect else None
        if pings:
            return list(pings.keys())
    except Exception as e:
        logger.error(f"API Health: Failed to check Celery workers: {e}")
    return []

@app.get("/health")
def get_health():
    """Verify core systems connectivity."""
    db_ok = check_db_health()
    redis_ok = check_redis_health()
    active_workers = check_celery_workers()
    workers_ok = len(active_workers) > 0
    
    # Assess playright library import as scraper validation check
    scraper_ok = False
    try:
        from playwright.sync_api import sync_playwright
        scraper_ok = True
    except ImportError:
        pass

    overall_status = "healthy"
    if not (db_ok and redis_ok and workers_ok):
        overall_status = "degraded"
        
    return {
        "status": overall_status,
        "services": {
            "postgres": "connected" if db_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
            "celery_workers": f"active ({len(active_workers)} workers)" if workers_ok else "no workers detected",
            "scrapers": "playwright_installed" if scraper_ok else "playwright_missing"
        }
    }

@app.get("/status")
def get_status():
    """Returns database summary stats and metrics."""
    db_ok = check_db_health()
    if not db_ok:
        raise HTTPException(status_code=503, detail="Database connection unavailable")
        
    stats = database.get_stats()
    
    with database.get_db() as session:
        from database import Campaign
        total_campaigns = session.query(Campaign).count()
        active_campaigns = session.query(Campaign).filter(Campaign.status == "active").count()
        
    return {
        "database_connected": True,
        "metrics": {
            "total_leads_scraped": stats["total"],
            "hot_leads": stats["tiers"].get("HOT", 0),
            "warm_leads": stats["tiers"].get("WARM", 0),
            "skipped_leads": stats["tiers"].get("SKIP", 0),
            "total_scheduled_campaigns": total_campaigns,
            "active_campaigns": active_campaigns
        }
    }

@app.get("/workers")
def get_workers_status():
    """Returns active worker details and queued tasks check."""
    active_workers = check_celery_workers()
    
    # Collect queues status
    active_tasks = {}
    try:
        inspect = celery_app.control.inspect()
        if inspect:
            active_tasks = inspect.active() or {}
    except Exception as e:
        logger.error(f"API Health: Failed to get Celery tasks list: {e}")
        
    return {
        "active_workers_count": len(active_workers),
        "active_workers_list": active_workers,
        "current_active_tasks": active_tasks
    }
