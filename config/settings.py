"""
config/settings.py - Base configurations for the Lead Platform.
Loads environment variables and maps them dynamically.

CLOUD COMPATIBILITY NOTE:
  OUTPUTS_FOLDER resolves to /tmp/lead_agent_exports when BASE_DIR is not writable
  (e.g., read-only container filesystems on Railway, Render, or Fly.io).
  This guarantees the bot never crashes with [Errno 13] Permission denied on file saves.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
load_dotenv()

ENV = os.getenv("ENV", "production").lower()

# Folders
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------
# Safe writable export folder resolution
# Priority: $EXPORTS_FOLDER env var → /app/exports → /tmp/lead_exports
# This fixes [Errno 13] Permission denied crashes on cloud platforms.
# ---------------------------------------------------------------
def _resolve_exports_folder() -> Path:
    """Return a guaranteed-writable folder for Excel exports."""
    # 1. Explicit override from environment
    env_override = os.getenv("EXPORTS_FOLDER", "")
    if env_override:
        p = Path(env_override)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            pass

    # 2. Try /app/exports (Docker standard mount)
    for candidate in [BASE_DIR / "exports", Path("/app/exports"), Path("/tmp/lead_exports")]:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            # Quick write permission test
            test_file = candidate / ".write_test"
            test_file.touch()
            test_file.unlink()
            return candidate
        except OSError:
            continue

    # 3. Last resort: OS temp directory
    fallback = Path(tempfile.gettempdir()) / "lead_exports"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _resolve_log_folder() -> Path:
    """Return a guaranteed-writable folder for log files."""
    for candidate in [BASE_DIR / "logs", Path("/app/logs"), Path("/tmp/lead_logs")]:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            test_file = candidate / ".write_test"
            test_file.touch()
            test_file.unlink()
            return candidate
        except OSError:
            continue
    fallback = Path(tempfile.gettempdir()) / "lead_logs"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


OUTPUTS_FOLDER = _resolve_exports_folder()
LOG_FOLDER = _resolve_log_folder()

print(f"[Config] Exports folder: {OUTPUTS_FOLDER}")
print(f"[Config] Logs folder:    {LOG_FOLDER}")

# Central Credentials & Connection URLs
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Scoring & Filter Thresholds
MIN_SCORE_TO_QUALIFY = 60
HOT_SCORE_THRESHOLD = 80
WARM_SCORE_THRESHOLD = 60

# Processing Options
REQUEST_DELAY_MIN = 2
REQUEST_DELAY_MAX = 5
WEBSITE_TIMEOUT = 8
MAX_RETRIES = 3
SCRAPER_WORKERS = 4
WEBSITE_ANALYSER_WORKERS = 10

# Rotating User Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
]

# Supported business categories / industries
INDUSTRY_KEYWORDS = [
    "restaurant", "dentist", "dental", "real estate",
    "manufacturer", "hotel", "hospital", "clinic",
    "gym", "salon", "school", "college", "lawyer",
    "ca firm", "chartered accountant", "interior designer"
]

# Supported cities / location keywords
LOCATION_KEYWORDS = [
    "Chennai", "Bangalore", "Mumbai", "Delhi",
    "Guindy", "Anna Nagar", "Velachery", "Adyar",
    "Tamil Nadu", "Karnataka", "Maharashtra"
]
