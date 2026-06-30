"""
main.py — Core entry point and local CLI orchestrator.
Allows running the 8-layer pipeline synchronously, or spawning bot / api / scheduler / agent services.
"""
from __future__ import annotations

import os
import sys
import time
import argparse
import logging
from datetime import datetime

# Initialize logging before local imports
import config
from monitoring import setup_logging

logger = setup_logging("pipeline_orchestrator")

import database
from scrapers import run_scrapers_parallel
from analytics.activity_detector import detect_activity_batch
from analytics.website_analyser import audit_leads_websites
from analytics.email_finder import process_leads_emails
from analytics.business_intelligence import analyze_business_batch
from analytics.pain_point_engine import process_pain_intelligence_batch
from analytics.scorer import score_and_filter_leads
from analytics.exporter import export_to_excel

def run_lead_pipeline(industry: str, location: str, limit: int, query_text: str = "") -> dict:
    """Run the entire lead intelligence pipeline from start to finish (synchronous CLI mode)."""
    start_time = time.time()
    
    print("=" * 70)
    print("AI LEAD GENERATION PLATFORM PIPELINE STARTING")
    print(f"Industry: {industry} | Location: {location} | Limit: {limit}")
    print("=" * 70)
    
    # Step 1: Initialize Database
    logger.info("Initializing database...")
    database.init_db()
    
    # Step 2: Parallel scraping
    logger.info("Starting multi-source scrapers...")
    unique_leads = run_scrapers_parallel(industry, location, limit)
    
    if not unique_leads:
        logger.warning("No leads found. Pipeline aborted.")
        print("[Pipeline] Scrapers returned 0 unique leads. Terminating pipeline.")
        return {
            "total_scraped": 0,
            "qualified_leads": 0,
            "duration": f"{round(time.time() - start_time, 2)}s",
            "excel_path": ""
        }
        
    logger.info("Saving initial scraped leads...")
    database.save_leads_bulk(unique_leads)
    
    # Layer 1: Activity Detection
    logger.info("Running Layer 1: Activity Detection...")
    active_leads = detect_activity_batch(unique_leads, reject_inactive=True)
    if not active_leads:
        logger.warning("No active leads found. Pipeline aborted.")
        print("[Pipeline] 0 active leads remain after Layer 1. Terminating pipeline.")
        return {
            "total_scraped": len(unique_leads),
            "qualified_leads": 0,
            "duration": f"{round(time.time() - start_time, 2)}s",
            "excel_path": ""
        }
        
    # Layer 2+3: Website Auditing
    logger.info("Running Layer 2+3: Website Auditing and Status Classification...")
    audited_leads = audit_leads_websites(active_leads)
    
    # Step 4: Email Discovery
    logger.info("Starting email intelligence discovery...")
    leads_with_emails = process_leads_emails(audited_leads)

    # Layer 4: Business Intelligence
    logger.info("Running Layer 4: Business Intelligence Extraction...")
    biz_leads = analyze_business_batch(leads_with_emails)

    # Layer 5+6+7: Pain Point Detection & Outreach Angle
    logger.info("Running Layer 5+6+7: Pain Points and Outreach Generation...")
    leads_with_pains = process_pain_intelligence_batch(biz_leads)
    
    # Layer 8: Lead Scoring & Filtering
    logger.info("Running Layer 8: Lead Scoring and Qualification...")
    final_leads = score_and_filter_leads(leads_with_pains, query_text)
    
    # Step 6: Export results
    logger.info("Generating Excel reports...")
    excel_path = ""
    if final_leads:
        excel_path = export_to_excel(final_leads, industry, location)
        print(f"[Pipeline] Export completed: {excel_path}")
    else:
        logger.warning("No leads qualified. Skipping Excel export.")
        print("[Pipeline] 0 leads qualified after filtering. Excel export skipped.")
        
    duration = time.time() - start_time
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
    
    print("=" * 70)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print(f"Total Unique Scraped: {len(unique_leads)}")
    print(f"Total Qualified: {len(final_leads)}")
    print(f"Duration: {duration_str}")
    print("=" * 70)
    
    return {
        "total_scraped": len(unique_leads),
        "qualified_leads": len(final_leads),
        "duration": duration_str,
        "excel_path": excel_path,
        "leads": final_leads
    }

def main() -> int:
    parser = argparse.ArgumentParser(description="Lead Orchestrator Entrypoint")
    parser.add_argument("--industry", "-i", default="dentist", help="Target industry")
    parser.add_argument("--location", "-l", default="Guindy", help="Target location")
    parser.add_argument("--limit", "-c", type=int, default=5, help="Limit per source")
    parser.add_argument("--filter", "-f", default="", help="Optional filter string matching user request")
    parser.add_argument("--test", action="store_true", help="Run a quick 2-lead test run")
    parser.add_argument("--service", choices=["bot", "api", "scheduler", "agent", "run-local"], help="Start a specific service background daemon")
    
    args = parser.parse_args()
    
    if args.service:
        if args.service == "bot":
            logger.info("Starting Telegram Bot Polling service...")
            from bot.bot_app import run_bot
            run_bot()
        elif args.service == "api":
            logger.info("Starting FastAPI Monitoring API service...")
            import uvicorn
            uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)
        elif args.service == "scheduler":
            logger.info("Starting APScheduler campaigns daemon...")
            from scheduler.scheduler.py import run_scheduler # Wait, scheduler is imported from scheduler.scheduler
            from scheduler.scheduler import run_scheduler
            run_scheduler()
        elif args.service == "agent":
            logger.info("Starting Self-Healing Watchdog service...")
            from workers.self_healing import run_watchdog_loop
            run_watchdog_loop()
        elif args.service == "run-local":
            run_lead_pipeline(args.industry, args.location, args.limit, args.filter)
        return 0
        
    if args.test:
        print("[Pipeline Test] Initiating quick test run (limit 2, Guindy)...")
        results = run_lead_pipeline("dentist", "Guindy", 2, args.filter)
        print(f"[Pipeline Test] Complete. Scraped: {results['total_scraped']} | Qualified: {results['qualified_leads']}")
        return 0
        
    run_lead_pipeline(args.industry, args.location, args.limit, args.filter)
    return 0

if __name__ == "__main__":
    sys.exit(main())