"""
workers/tasks.py - Core Celery tasks for asynchronous lead intelligence processing.
"""
from __future__ import annotations

import os
import time
import logging
import requests
from datetime import datetime
from celery import shared_task

import config
import database
from scrapers import run_scrapers_parallel
from analytics.activity_detector import detect_activity_batch
from analytics.website_analyser import audit_leads_websites
from analytics.email_finder import process_leads_emails
from analytics.business_intelligence import analyze_business_batch
from analytics.pain_point_engine import process_pain_intelligence_batch
from analytics.scorer import score_and_filter_leads
from analytics.exporter import export_to_excel
from analytics.progress import send_telegram_update

logger = logging.getLogger(__name__)

def send_telegram_document(chat_id: str | int | None, filepath: str, caption: str = "") -> bool:
    """Uploads and sends a document file directly to a Telegram chat."""
    if not chat_id or not config.TELEGRAM_BOT_TOKEN:
        return False
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(filepath, "rb") as f:
            files = {"document": f}
            data = {"chat_id": str(chat_id), "caption": caption}
            resp = requests.post(url, data=data, files=files, timeout=45)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram document: {e}")
        return False

@shared_task(bind=True, max_retries=3, default_retry_delay=900)  # Retry in 15 minutes
def run_lead_pipeline_task(
    self,
    job_id: str,
    industry: str,
    location: str,
    limit: int,
    query_text: str = "",
    telegram_chat_id: str | None = None,
    user_id: str | None = None
) -> dict:
    """
    Executes the entire 8-layer Lead Intelligence pipeline asynchronously.
    Updates the database with job progression and delivers the reports to Telegram.
    """
    start_time = time.time()
    
    # Step 1: Update job state to running in the database
    database.update_job_status(job_id, status="running")
    
    # Initialize DB (if Postgres server is restarting/cold)
    database.init_db()
    
    if user_id:
        # Create user profile and increment request counter
        database.create_user_if_not_exists(user_id)
        database.increment_user_request(user_id)

    msg = f"🚀 **Pipeline started** (Job ID: `{job_id}`)\n• Finding {limit} {industry} leads in {location}..."
    send_telegram_update(telegram_chat_id, msg)
    
    try:
        # Layer 1: Scrape
        send_telegram_update(telegram_chat_id, "🔍 *Step 1/8:* Scraping Google Maps, Google Site search, Justdial, and Sulekha in parallel...")
        unique_leads = run_scrapers_parallel(industry, location, limit)
        
        if not unique_leads:
            send_telegram_update(telegram_chat_id, "⚠️ Pipeline finished. Found 0 unique leads matching parameters.")
            database.update_job_status(job_id, status="success", finished=True)
            return {"total_scraped": 0, "qualified": 0}

        # Save initial unique leads
        database.save_leads_bulk(unique_leads)
        
        # Layer 2: Activity Detection
        send_telegram_update(telegram_chat_id, "⚡ *Step 2/8:* Detecting active businesses...")
        active_leads = detect_activity_batch(unique_leads, reject_inactive=True)
        if not active_leads:
            send_telegram_update(telegram_chat_id, "⚠️ Pipeline finished. 0 active leads remain after quality gates.")
            database.update_job_status(job_id, status="success", finished=True)
            return {"total_scraped": len(unique_leads), "qualified": 0}
            
        # Layer 3 & 4: Website Auditing
        send_telegram_update(telegram_chat_id, "🌐 *Step 3/8:* Running technical website audit (HTTPS, SSL, Speed, Mobile-readiness)...")
        audited_leads = audit_leads_websites(active_leads)
        
        # Layer 5: Email Discovery
        send_telegram_update(telegram_chat_id, "📧 *Step 4/8:* Attempting email intelligence discovery and MX record verification...")
        leads_with_emails = process_leads_emails(audited_leads)
        
        # Layer 6: Business Intelligence Extraction
        send_telegram_update(telegram_chat_id, "📊 *Step 5/8:* Extracting business intelligence (estimated size, budget, page content classification)...")
        biz_leads = analyze_business_batch(leads_with_emails)
        
        # Layer 7: Pain Points & Recommendations
        send_telegram_update(telegram_chat_id, "🛠️ *Step 6/8:* Scanning tech stacks for opportunities and recommended pitches...")
        leads_with_pains = process_pain_intelligence_batch(biz_leads)
        
        # Layer 8: Scoring & Filtering
        send_telegram_update(telegram_chat_id, "⭐ *Step 7/8:* Scoring leads and applying user query qualification criteria...")
        final_leads = score_and_filter_leads(leads_with_pains, query_text)
        
        # Step 6: Excel Reports
        send_telegram_update(telegram_chat_id, "📥 *Step 8/8:* Generating Apollo-style spreadsheets and platform-specific segments...")
        excel_path = ""
        if final_leads:
            excel_path = export_to_excel(final_leads, industry, location)
        else:
            send_telegram_update(telegram_chat_id, "❌ No leads qualified after scoring filters.")
            database.update_job_status(job_id, status="success", finished=True)
            return {"total_scraped": len(unique_leads), "qualified": 0}
            
        duration = time.time() - start_time
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        duration_str = f"{minutes}m {seconds}s" if minutes > 0 else f"{seconds}s"
        
        # Stats breakdown
        hot_leads = sum(1 for l in final_leads if l.get("tier") == "HOT")
        warm_leads = sum(1 for l in final_leads if l.get("tier") == "WARM")
        emails_count = sum(1 for l in final_leads if l.get("email_confidence") == "found")
        no_web = sum(1 for l in final_leads if not l.get("website"))
        outdated = sum(1 for l in final_leads if l.get("is_outdated", 0) == 1)
        no_chatbot = sum(1 for l in final_leads if l.get("has_chatbot", 1) == 0)
        
        top_lead = "None"
        top_score = 0
        top_pitch = "N/A"
        if final_leads:
            sorted_by_score = sorted(final_leads, key=lambda x: x.get("opportunity_score", 0), reverse=True)
            top_lead = sorted_by_score[0].get("business_name")
            top_score = sorted_by_score[0].get("opportunity_score", 0)
            top_pitch = sorted_by_score[0].get("recommended_pitch", "")

        summary_message = (
            f"✅ **Lead Campaign Complete!**\n\n"
            f"• Industry: {industry.title()}\n"
            f"• Location: {location.title()}\n"
            f"• Duration: {duration_str}\n\n"
            f"**Execution Metrics:**\n"
            f"• Scraped raw leads: {len(unique_leads)}\n"
            f"• Scored qualified leads: {len(final_leads)}\n\n"
            f"**Signal Breakdown:**\n"
            f"• HOT opportunities: {hot_leads}\n"
            f"• WARM opportunities: {warm_leads}\n"
            f"• Verified emails: {emails_count}\n"
            f"• Missing websites: {no_web}\n"
            f"• Outdated websites: {outdated}\n"
            f"• No chatbots: {no_chatbot}\n\n"
            f"🌟 **Top Lead:** {top_lead} — Score: {top_score}\n"
            f"👉 Recommended: {top_pitch}\n\n"
            f"📂 Spreadsheets are attached below."
        )
        
        send_telegram_update(telegram_chat_id, summary_message)
        
        # Send master Excel
        if excel_path and os.path.exists(excel_path):
            send_telegram_document(telegram_chat_id, excel_path, caption=os.path.basename(excel_path))
            
        # Send platform segments if they exist in the exports directory
        date_str = datetime.now().strftime("%Y-%m-%d")
        exports_folder = str(config.OUTPUTS_FOLDER)
        for platform in ["Instagram", "Linkedin", "Facebook"]:
            for file in os.listdir(exports_folder):
                if file.startswith(platform + "_Leads_") and date_str in file:
                    fp = os.path.join(exports_folder, file)
                    send_telegram_document(telegram_chat_id, fp, caption=file)
                    
        database.update_job_status(job_id, status="success", finished=True)
        return {"total_scraped": len(unique_leads), "qualified": len(final_leads)}
        
    except Exception as e:
        logger.exception(f"Pipeline crashed for job {job_id}")
        error_msg = str(e)
        database.update_job_status(job_id, status="failed", error_message=error_msg, finished=True)
        
        failure_msg = f"❌ **Pipeline Execution Crashed** (Job ID: `{job_id}`)\nError: {error_msg}\nRetrying automatically if allowed..."
        send_telegram_update(telegram_chat_id, failure_msg)
        
        # Propagate the task retry
        raise self.retry(exc=e)
