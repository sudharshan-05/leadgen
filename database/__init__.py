"""
database package entrypoint.
"""
from __future__ import annotations

from database.connection import get_db, engine
from database.models import User, Lead, Campaign, Job, Log
from database.crud import (
    init_db,
    deduplicate_check,
    save_lead,
    save_leads_bulk,
    get_stats,
    get_leads_by_filter,
    create_user_if_not_exists,
    increment_user_request,
    create_job,
    update_job_status,
    get_job,
    get_stuck_jobs,
    get_failed_retryable_jobs
)

__all__ = [
    "get_db",
    "engine",
    "User",
    "Lead",
    "Campaign",
    "Job",
    "Log",
    "init_db",
    "deduplicate_check",
    "save_lead",
    "save_leads_bulk",
    "get_stats",
    "get_leads_by_filter",
    "create_user_if_not_exists",
    "increment_user_request",
    "create_job",
    "update_job_status",
    "get_job",
    "get_stuck_jobs",
    "get_failed_retryable_jobs"
]
