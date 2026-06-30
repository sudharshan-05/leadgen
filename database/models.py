"""
database/models.py - Declarative database models.
Defines schema layout for users, leads, campaigns, jobs, and logs.
"""
from __future__ import annotations

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)  # Telegram User ID
    subscription_plan = Column(String, default="free")
    request_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_name = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    email_confidence = Column(String, nullable=True)
    website = Column(String, nullable=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)
    category = Column(String, nullable=True)
    source = Column(String, nullable=True)
    place_id = Column(String, unique=True, index=True, nullable=True)
    google_maps_url = Column(String, nullable=True)
    
    # Audit layers
    is_live = Column(Boolean, default=False)
    has_https = Column(Boolean, default=False)
    is_mobile_ready = Column(Boolean, default=False)
    has_chatbot = Column(Boolean, default=False)
    has_whatsapp = Column(Boolean, default=False)
    has_booking = Column(Boolean, default=False)
    is_outdated = Column(Boolean, default=False)
    copyright_year = Column(Integer, nullable=True)
    load_time = Column(Float, nullable=True)
    page_speed_score = Column(Integer, nullable=True)
    website_score = Column(Integer, nullable=True)
    cms_detected = Column(String, nullable=True)
    opportunity_score = Column(Integer, nullable=True)
    tier = Column(String, nullable=True)
    recommended_pitch = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    campaign_id = Column(Integer, nullable=True)
    raw_snippet = Column(String, nullable=True)
    
    # Enrichment layers
    business_active = Column(Boolean, default=True)
    activity_score = Column(Integer, nullable=True)
    ssl_valid = Column(Boolean, default=False)
    has_contact_form = Column(Boolean, default=False)
    has_sitemap = Column(Boolean, default=False)
    has_pricing_page = Column(Boolean, default=False)
    broken_links_count = Column(Integer, default=0)
    website_status_label = Column(String, nullable=True)
    website_status_confidence = Column(Float, nullable=True)
    detected_technologies = Column(String, nullable=True)
    company_summary = Column(String, nullable=True)
    industry_detected = Column(String, nullable=True)
    services_list = Column(String, nullable=True)
    location_count = Column(Integer, default=1)
    company_size = Column(String, nullable=True)
    budget_level = Column(String, nullable=True)
    pain_points = Column(String, nullable=True)
    recommended_services = Column(String, nullable=True)
    outreach_angle = Column(String, nullable=True)

# Performance indexes
Index('idx_leads_phone', Lead.phone)
Index('idx_leads_email', Lead.email)
Index('idx_leads_city', Lead.city)
Index('idx_leads_tier', Lead.tier)
Index('idx_leads_opportunity_score', Lead.opportunity_score)


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    industry = Column(String, nullable=False)
    location = Column(String, nullable=False)
    count = Column(Integer, default=10)
    frequency = Column(String, default="daily")  # daily, weekly, monthly
    run_time = Column(String, default="08:00")
    day_of_week = Column(String, nullable=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    status = Column(String, default="active")  # active, paused
    telegram_chat_id = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class Job(Base):
    __tablename__ = "jobs"

    job_id = Column(String, primary_key=True)  # Celery task_id
    status = Column(String, default="pending")  # pending, running, success, failed, stuck
    retry_count = Column(Integer, default=0)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    industry = Column(String, nullable=False)
    location = Column(String, nullable=False)
    limit = Column(Integer, default=10)
    filters = Column(String, nullable=True)
    telegram_chat_id = Column(String, nullable=True)
    user_id = Column(String, nullable=True)
    error_message = Column(String, nullable=True)


class Log(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(Integer, nullable=True)
    run_at = Column(DateTime, default=datetime.datetime.utcnow)
    leads_scraped = Column(Integer, default=0)
    leads_qualified = Column(Integer, default=0)
    excel_path = Column(String, nullable=True)
    status = Column(String, nullable=False)  # success, failed
    error_message = Column(String, nullable=True)
