"""
database/connection.py - SQLAlchemy connection setup.
Provides session engine and session context helper.

Railway/Render Compatibility:
  - Automatically converts 'postgres://' to 'postgresql://' (Railway uses the
    old postgres:// scheme which SQLAlchemy 1.4+ rejects with an error).
  - Retries connection up to 5 times on startup to handle cold-boot race
    conditions (container starts before database is fully ready).
"""
from __future__ import annotations

import time
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------
# Railway Fix: postgres:// -> postgresql://
# Railway provides DATABASE_URL starting with "postgres://" but
# SQLAlchemy 1.4+ only accepts "postgresql://". This one line
# fixes the "Could not parse rfc1738 URL" crash on Railway.
# ---------------------------------------------------------------
_db_url = DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    logger.info("database/connection.py: Rewrote postgres:// -> postgresql:// for SQLAlchemy compatibility")

# SQLite needs check_same_thread=False for multi-threaded access
connect_args = {}
if _db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# ---------------------------------------------------------------
# Retry engine creation up to 5 times
# Handles Docker/Railway cold-boot race where DB isn't ready yet
# ---------------------------------------------------------------
_MAX_RETRIES = 5
_RETRY_DELAY = 5  # seconds

engine = None
SessionLocal = None

for attempt in range(1, _MAX_RETRIES + 1):
    try:
        engine = create_engine(
            _db_url,
            connect_args=connect_args,
            pool_pre_ping=True,       # Test connection before each use
            pool_recycle=300,         # Recycle connections every 5 minutes
            pool_timeout=30,          # Wait max 30s for a pool connection
            pool_size=5,              # Max 5 persistent connections per worker
            max_overflow=10,          # Allow 10 extra connections at peak
        )
        # Quick connection test to verify DB is reachable
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        logger.info(f"Database connected successfully on attempt {attempt}.")
        break
    except Exception as e:
        logger.warning(f"Database connection attempt {attempt}/{_MAX_RETRIES} failed: {e}")
        if attempt < _MAX_RETRIES:
            logger.info(f"Retrying in {_RETRY_DELAY} seconds...")
            time.sleep(_RETRY_DELAY)
        else:
            logger.exception("All database connection attempts failed. Giving up.")
            raise RuntimeError(
                f"Could not connect to database after {_MAX_RETRIES} attempts. "
                f"Check DATABASE_URL environment variable. URL used: {_db_url[:40]}..."
            ) from e


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
