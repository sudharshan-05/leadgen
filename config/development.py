"""
config/development.py - Development environment overrides.
"""
from __future__ import annotations
import os
from config.settings import BASE_DIR

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/lead_agent.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEBUG = True
