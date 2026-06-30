"""
config/production.py - Production environment configurations.
"""
from __future__ import annotations
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/lead_agent")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
DEBUG = False
