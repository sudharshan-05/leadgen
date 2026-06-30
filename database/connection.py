"""
database/connection.py - SQLAlchemy connection setup.
Provides session engine and session context helper.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# Check if SQLite to adjust connection arguments
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.exception("Failed to initialize SQLAlchemy engine")
    raise e

@contextmanager
def get_db():
    """Context manager to yield database session and close it automatically."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
