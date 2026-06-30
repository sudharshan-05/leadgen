#!/usr/bin/env python3
"""
railway_env_check.py - Pre-deployment environment variable validator.
Run this before pushing to Railway to catch missing configs early.
"""
import os
import sys

REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "DATABASE_URL",
    "REDIS_URL",
]

OPTIONAL_VARS = [
    "SENTRY_DSN",
    "GOOGLE_MAPS_API_KEY",
    "EXPORTS_FOLDER",
]

def check():
    print("=" * 55)
    print("  Lead Agent - Railway Deployment Pre-Check")
    print("=" * 55)

    all_ok = True
    for var in REQUIRED_VARS:
        val = os.getenv(var, "")
        if not val:
            print(f"  [MISSING] REQUIRED: {var}")
            all_ok = False
        else:
            masked = val[:8] + "..." if len(val) > 8 else "***"
            print(f"  [OK] {var} = {masked}")

    for var in OPTIONAL_VARS:
        val = os.getenv(var, "")
        if val:
            print(f"  [OK] {var} = {val[:8]}...")
        else:
            print(f"  [SKIP] {var} not set (optional)")

    print("=" * 55)
    if all_ok:
        print("  [PASS] All required variables set. Safe to deploy!")
    else:
        print("  [FAIL] Set the missing variables before deploying.")
        sys.exit(1)

if __name__ == "__main__":
    # Load .env if it exists locally
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    check()
