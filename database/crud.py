"""
database/crud.py - Database helper functions.
Implements lead upserts, deduplication checks, stats generation, filters, jobs and user tracking.
"""
from __future__ import annotations

import re
import logging
import datetime
from urllib.parse import urlparse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from rapidfuzz import fuzz

from database.connection import engine, get_db
from database.models import Base, Lead, User, Campaign, Job, Log

logger = logging.getLogger(__name__)

def init_db() -> bool:
    """Initialize tables in the configured database."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully.")
        return True
    except Exception as e:
        logger.exception("Failed to initialize database tables")
        return False

def _normalize_phone_helper(phone: str) -> str:
    """Normalize phone number by stripping spaces, dashes, +91, and leading 0."""
    if not phone:
        return ""
    clean = re.sub(r"[\s\-\(\)\+]", "", phone.strip())
    if clean.startswith("91") and len(clean) > 10:
        clean = clean[2:]
    elif clean.startswith("0") and len(clean) > 9:
        clean = clean[1:]
    return clean

def _extract_domain_helper(url: str) -> str:
    """Extract root domain from website URL."""
    if not url:
        return ""
    try:
        url_lower = url.strip().lower()
        if not url_lower.startswith(("http://", "https://")):
            url_lower = "http://" + url_lower
        parsed = urlparse(url_lower)
        netloc = parsed.netloc
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""

def deduplicate_check(phone: str | None, domain: str | None, name: str | None, city: str | None = None) -> bool:
    """
    Check if a duplicate exists in the database.
    Checks phone number matches, domain matches, and fuzzy name matches.
    """
    with get_db() as session:
        # 1. Phone number match
        if phone:
            norm_phone = _normalize_phone_helper(phone)
            if norm_phone:
                db_phones = session.query(Lead.phone).filter(Lead.phone.isnot(None), Lead.phone != "").all()
                for (db_p,) in db_phones:
                    if _normalize_phone_helper(db_p) == norm_phone:
                        return True

        # 2. Domain match
        if domain:
            target_domain = domain.strip().lower()
            if target_domain.startswith("www."):
                target_domain = target_domain[4:]
            
            db_websites = session.query(Lead.website).filter(Lead.website.isnot(None), Lead.website != "").all()
            for (db_w,) in db_websites:
                db_dom = _extract_domain_helper(db_w)
                if db_dom == target_domain:
                    return True

        # 3. Fuzzy name match (> 85% similarity AND same city)
        if name:
            target_name = name.strip().lower()
            db_leads = session.query(Lead.business_name, Lead.address, Lead.city).filter(Lead.business_name.isnot(None)).all()
            for db_name, db_address, db_city in db_leads:
                db_name_clean = db_name.strip().lower()
                sim = fuzz.token_sort_ratio(target_name, db_name_clean)
                if sim > 85:
                    clean_db_city = (db_city or "").strip().lower()
                    if not clean_db_city and db_address:
                        addr = db_address.lower()
                        if city and city.lower() in addr:
                            return True
                    elif city and clean_db_city == city.strip().lower():
                        return True
                    elif not city:
                        return True

    return False

def save_lead(lead_data: dict) -> bool:
    """Insert or update a single lead in the database."""
    try:
        place_id = lead_data.get("place_id")
        with get_db() as session:
            existing_lead = None
            if place_id:
                existing_lead = session.query(Lead).filter(Lead.place_id == place_id).first()

            if existing_lead:
                # Update properties except ID, created_at, and campaign_id
                for key, val in lead_data.items():
                    if key not in ("id", "created_at", "campaign_id") and hasattr(existing_lead, key):
                        setattr(existing_lead, key, val)
            else:
                # Insert new Lead
                lead_obj = Lead()
                for key, val in lead_data.items():
                    if hasattr(lead_obj, key):
                        setattr(lead_obj, key, val)
                session.add(lead_obj)
        return True
    except Exception as e:
        logger.error(f"Failed to save lead: {e}")
        return False

def save_leads_bulk(leads: list[dict]) -> int:
    """Save a list of leads to PostgreSQL database in a single transaction."""
    saved_count = 0
    if not leads:
        return 0
    try:
        with get_db() as session:
            for lead in leads:
                place_id = lead.get("place_id")
                existing_lead = None
                if place_id:
                    existing_lead = session.query(Lead).filter(Lead.place_id == place_id).first()

                if existing_lead:
                    for key, val in lead.items():
                        if key not in ("id", "created_at", "campaign_id") and hasattr(existing_lead, key):
                            setattr(existing_lead, key, val)
                else:
                    lead_obj = Lead()
                    for key, val in lead.items():
                        if hasattr(lead_obj, key):
                            setattr(lead_obj, key, val)
                    session.add(lead_obj)
                saved_count += 1
        return saved_count
    except Exception as e:
        logger.error(f"Failed to save leads in bulk: {e}")
        return 0

def get_stats() -> dict:
    """Return summary statistics about the database."""
    stats = {"tiers": {}, "sources": {}, "total": 0}
    try:
        with get_db() as session:
            stats["total"] = session.query(Lead).count()
            
            tiers = session.query(Lead.tier, func.count(Lead.id)).group_by(Lead.tier).all()
            for tier, count in tiers:
                stats["tiers"][tier or "SKIP"] = count
                
            sources = session.query(Lead.source, func.count(Lead.id)).group_by(Lead.source).all()
            for source, count in sources:
                stats["sources"][source or "unknown"] = count
    except Exception as e:
        logger.error(f"Error querying database stats: {e}")
    return stats

def get_leads_by_filter(filters: dict) -> list[dict]:
    """
    Query leads based on criteria.
    Supported keys: city, category, source, tier, min_score, rating_above, no_website, no_chatbot, outdated, has_email
    """
    leads = []
    try:
        with get_db() as session:
            query = session.query(Lead)
            
            if filters.get("city"):
                query = query.filter(Lead.city.ilike(f"%{filters['city']}%"))
                
            if filters.get("source"):
                query = query.filter(Lead.source == filters["source"])
                
            if filters.get("tier"):
                query = query.filter(Lead.tier == filters["tier"])
                
            if filters.get("min_score") is not None:
                query = query.filter(Lead.opportunity_score >= filters["min_score"])
                
            if filters.get("rating_above") is not None:
                query = query.filter(Lead.rating >= filters["rating_above"])
                
            if filters.get("no_website"):
                query = query.filter(or_(Lead.website.is_(None), Lead.website == "", Lead.is_live.is_(False)))
                
            if filters.get("no_chatbot"):
                query = query.filter(Lead.has_chatbot.is_(False))
                
            if filters.get("outdated"):
                query = query.filter(Lead.is_outdated.is_(True))
                
            if filters.get("has_email"):
                query = query.filter(Lead.email.isnot(None), Lead.email != "", Lead.email_confidence == "found")
                
            query = query.order_by(Lead.opportunity_score.desc())
            results = query.all()
            
            # Convert models to dictionaries
            for r in results:
                d = {col.name: getattr(r, col.name) for col in r.__table__.columns}
                leads.append(d)
    except Exception as e:
        logger.error(f"Error querying filtered leads: {e}")
    return leads

# ===========================================================================
# USER MANAGEMENT & JOBS TRACKING
# ===========================================================================

def create_user_if_not_exists(user_id: str, plan: str = "free") -> User:
    """Create a new user profile if it does not already exist."""
    with get_db() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            user = User(user_id=user_id, subscription_plan=plan)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user

def increment_user_request(user_id: str) -> None:
    """Increment request counter for user."""
    with get_db() as session:
        user = session.query(User).filter(User.user_id == user_id).first()
        if user:
            user.request_count += 1

def create_job(job_id: str, industry: str, location: str, limit: int, filters: str | None, telegram_chat_id: str | None, user_id: str | None) -> Job:
    """Create an asynchronous job record."""
    with get_db() as session:
        job = Job(
            job_id=job_id,
            status="pending",
            retry_count=0,
            industry=industry,
            location=location,
            limit=limit,
            filters=filters,
            telegram_chat_id=telegram_chat_id,
            user_id=user_id
        )
        session.add(job)
        return job

def update_job_status(job_id: str, status: str, error_message: str | None = None, finished: bool = False, inc_retry: bool = False) -> Job | None:
    """Update async job state details."""
    with get_db() as session:
        job = session.query(Job).filter(Job.job_id == job_id).first()
        if job:
            job.status = status
            if error_message:
                job.error_message = error_message
            if finished:
                job.finished_at = datetime.datetime.utcnow()
            if inc_retry:
                job.retry_count += 1
            return job
    return None

def get_job(job_id: str) -> Job | None:
    """Fetch job details."""
    with get_db() as session:
        return session.query(Job).filter(Job.job_id == job_id).first()

def get_stuck_jobs(timeout_minutes: int = 30) -> list[Job]:
    """Retrieve jobs marked as running but have exceeded threshold duration."""
    threshold = datetime.datetime.utcnow() - datetime.timedelta(minutes=timeout_minutes)
    with get_db() as session:
        return session.query(Job).filter(Job.status == "running", Job.started_at <= threshold).all()

def get_failed_retryable_jobs(max_retries: int = 3) -> list[Job]:
    """Retrieve failed jobs that can be retried."""
    with get_db() as session:
        return session.query(Job).filter(Job.status == "failed", Job.retry_count < max_retries).all()
