"""
bot/bot_app.py — Production Telegram Bot Interface.
Asynchronously queues scraping requests to Celery and queries PostgreSQL via SQLAlchemy.
"""
from __future__ import annotations

import os
import re
import uuid
import asyncio
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters as tg_filters
)

import config
import database
from database import get_db, Campaign, Job
from analytics.scorer import parse_request_filters
from analytics.exporter import export_to_excel
from workers.tasks import run_lead_pipeline_task
from monitoring import setup_logging, init_sentry

logger = setup_logging("telegram_bot")
init_sentry("telegram_bot")

def parse_natural_query(text: str) -> tuple[int, str, str, str]:
    """Parse natural language query into count, industry, location, and filters."""
    text_lower = text.lower()
    
    nums = re.findall(r"\b(\d+)\b", text)
    count = 10
    if nums:
        for num in nums:
            if f"rating above {num}" not in text_lower and f"above {num}" not in text_lower:
                count = int(num)
                break
                
    industry = ""
    for kw in config.INDUSTRY_KEYWORDS:
        if kw in text_lower:
            industry = kw
            break
    if not industry:
        words = text.split()
        if len(words) > 2:
            industry = " ".join(words[2:4])
        else:
            industry = "real estate"
            
    location = ""
    for kw in config.LOCATION_KEYWORDS:
        if kw.lower() in text_lower:
            location = kw
            break
    if not location:
        match_loc = re.search(r"\bin\s+([a-zA-Z\s]+)", text)
        if match_loc:
            candidate = match_loc.group(1).strip()
            candidate = re.split(r"\b(qualified|high|no|with|has|rating)\b", candidate)[0].strip()
            if candidate:
                location = candidate
        else:
            location = "Guindy"
            
    filter_list = []
    for f_kw in ["qualified", "high opportunity", "no website", "outdated", "no chatbot", "has email"]:
        if f_kw in text_lower:
            filter_list.append(f_kw)
    match_rating = re.search(r"rating above\s+(\d+(\.\d+)?)", text_lower)
    if match_rating:
        filter_list.append(match_rating.group(0))
        
    filter_str = ", ".join(filter_list)
    return count, industry, location, filter_str

# ===========================================================================
# COMMAND HANDLERS
# ===========================================================================

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explains command usage."""
    help_text = (
        "🤖 **Lead Intelligence Platform Bot**\n\n"
        "Control pipeline execution and scheduled campaigns:\n"
        "• `/find [count] [industry] [location] [filters]` — Run scraping\n"
        "• `/status` — View platform stats\n"
        "• `/schedule [daily/weekly/monthly] [count] [industry] [location]` — Schedule recurring find\n"
        "• `/campaigns` — List active schedules\n"
        "• `/pause [id]` / `/resume [id]` — Pause or resume campaigns\n"
        "• `/export [industry] [location]` — Re-export existing database leads\n"
        "• `/filter [criteria]` — Query and export leads matching criteria\n\n"
        "💬 *Supports natural language too!* Try sending:\n"
        "\"give me 15 qualified leads for salons in Guindy\""
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def find_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Queues a background lead scraping job to Celery."""
    args_text = " ".join(context.args) if context.args else ""
    if not args_text:
        await update.message.reply_text(
            "⚠️ Usage: `/find [count] [industry] [location] [optional filters]`\n"
            "Example: `/find 30 dentists Chennai qualified`"
        )
        return
        
    count, industry, location, filters = parse_natural_query(args_text)
    chat_id = str(update.effective_chat.id)
    user_id = str(update.effective_user.id) if update.effective_user else None
    
    # Generate job ID and register in PostgreSQL
    job_id = str(uuid.uuid4())
    database.create_job(
        job_id=job_id,
        industry=industry,
        location=location,
        limit=count,
        filters=filters,
        telegram_chat_id=chat_id,
        user_id=user_id
    )
    
    # Queue task to Celery asynchronously
    run_lead_pipeline_task.apply_async(
        args=[job_id, industry, location, count, filters],
        kwargs={"telegram_chat_id": chat_id, "user_id": user_id},
        task_id=job_id
    )
    
    confirm_text = (
        f"🚀 **Search campaign registered & queued!**\n"
        f"• Job ID: `{job_id}`\n"
        f"• Industry: {industry.title()}\n"
        f"• Location: {location.title()}\n"
        f"• Targets: {count} leads | Filters: {filters or 'None'}\n\n"
        f"⏱️ I am running the scraping pipeline in the background. I will notify you and upload reports here as soon as they are completed!"
    )
    await update.message.reply_text(confirm_text, parse_mode="Markdown")

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Replies with database status metrics."""
    stats = database.get_stats()
    
    # Active campaigns count
    with get_db() as session:
        active_scheds = session.query(Campaign).filter(Campaign.status == "active").count()
        last_row = session.query(Job.started_at).order_by(Job.started_at.desc()).first()
        last_time = last_row[0].strftime("%Y-%m-%d %H:%M:%S") if last_row else "Never"
        
    hot = stats["tiers"].get("HOT", 0)
    warm = stats["tiers"].get("WARM", 0)
    
    status_text = (
        f"📊 **System Status**\n\n"
        f"• Total leads in database: {stats['total']}\n"
        f"• HOT opportunity leads: {hot}\n"
        f"• WARM opportunity leads: {warm}\n"
        f"• Last search executed: {last_time} UTC\n"
        f"• Active schedules: {active_scheds}\n"
        f"• System status: **Running normally**"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")

async def schedule_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Saves a recurring campaign scheduler row."""
    if len(context.args) < 4:
        await update.message.reply_text(
            "⚠️ Usage: `/schedule [daily/weekly/monthly] [count] [industry] [location]`\n"
            "Example: `/schedule daily 50 real estate Guindy`"
        )
        return
        
    frequency = context.args[0].lower()
    if frequency not in ["daily", "weekly", "monthly"]:
        await update.message.reply_text("❌ Frequency must be daily, weekly, or monthly.")
        return
        
    try:
        count = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Count must be an integer.")
        return
        
    industry = context.args[2].lower()
    location = " ".join(context.args[3:]).lower()
    chat_id = str(update.effective_chat.id)
    
    # Calculate initial next run
    now = datetime.utcnow()
    if frequency == "daily":
        next_run = now + timedelta(days=1)
    elif frequency == "weekly":
        next_run = now + timedelta(weeks=1)
    else:
        next_run = now + timedelta(days=30)
        
    # Save campaign schedule to DB via SQLAlchemy
    with get_db() as session:
        campaign = Campaign(
            name=f"{frequency} {count} {industry} {location}",
            industry=industry,
            location=location,
            count=count,
            frequency=frequency,
            run_time="08:00",
            day_of_week="monday" if frequency == "weekly" else None,
            next_run=next_run,
            telegram_chat_id=chat_id,
            status="active"
        )
        session.add(campaign)
        
    await update.message.reply_text(
        f"📅 **Scheduled Campaign Registered!**\n"
        f"I will automatically search for {count} {industry} leads in {location} **{frequency}** and upload results here."
    )

async def campaigns_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all active and paused campaigns."""
    with get_db() as session:
        rows = session.query(Campaign).all()
        
    if not rows:
        await update.message.reply_text("📭 No campaigns scheduled.")
        return
        
    text_list = ["📋 **Scheduled Campaigns:**"]
    for row in rows:
        status_tag = "✅ Active" if row.status == "active" else "⏸️ Paused"
        next_run_str = row.next_run.strftime("%Y-%m-%d %H:%M:%S") if row.next_run else "Pending"
        text_list.append(
            f"{row.id}. **{row.frequency.title()}** — {row.count} {row.industry} in {row.location}\n"
            f"   • Next run: {next_run_str} UTC\n"
            f"   • Status: {status_tag}"
        )
        
    await update.message.reply_text("\n".join(text_list), parse_mode="Markdown")

async def pause_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pauses a campaign schedule by campaign_id."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/pause [campaign_id]`")
        return
    c_id = int(context.args[0])
    
    with get_db() as session:
        campaign = session.query(Campaign).filter(Campaign.id == c_id).first()
        if campaign:
            campaign.status = "paused"
            
    await update.message.reply_text(f"⏸️ Campaign ID {c_id} has been **paused**.")

async def resume_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumes a campaign schedule by campaign_id."""
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/resume [campaign_id]`")
        return
    c_id = int(context.args[0])
    
    with get_db() as session:
        campaign = session.query(Campaign).filter(Campaign.id == c_id).first()
        if campaign:
            campaign.status = "active"
            
    await update.message.reply_text(f"✅ Campaign ID {c_id} has been **resumed**.")

async def export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Re-exports leads matching target parameters from PostgreSQL directly."""
    if len(context.args) < 2:
        await update.message.reply_text("⚠️ Usage: `/export [industry] [location]`")
        return
        
    industry = context.args[0].lower()
    location = " ".join(context.args[1:]).lower()
    
    await update.message.reply_text(f"📂 Querying database for existing `{industry}` leads in `{location}`...")
    
    leads = database.get_leads_by_filter({"city": location})
    leads = [l for l in leads if industry in str(l.get("category", "")).lower() or industry in str(l.get("business_name", "")).lower()]
    
    if not leads:
        await update.message.reply_text("❌ No matching leads found in the database. Scrape them first using `/find`.")
        return
        
    excel_path = export_to_excel(leads, industry, location)
    
    with open(excel_path, "rb") as f:
        await update.message.reply_document(f, filename=os.path.basename(excel_path))
        
    await update.message.reply_text(f"✅ Re-exported {len(leads)} leads from database.")

async def filter_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Directly filters database and exports qualified leads."""
    args_text = " ".join(context.args) if context.args else ""
    if not args_text:
        await update.message.reply_text("⚠️ Usage: `/filter [score above X / no chatbot / outdated]`")
        return
        
    filters = parse_request_filters(args_text)
    
    db_filters = {}
    if filters.get("qualified"):
        db_filters["min_score"] = 60
    if filters.get("high opportunity"):
        db_filters["min_score"] = 75
    if filters.get("no_website"):
        db_filters["no_website"] = True
    if filters.get("outdated"):
        db_filters["outdated"] = True
    if filters.get("no_chatbot"):
        db_filters["no_chatbot"] = True
    if filters.get("has_email"):
        db_filters["has_email"] = True
    if filters.get("rating_above") is not None:
        db_filters["rating_above"] = filters["rating_above"]
        
    for kw in config.LOCATION_KEYWORDS:
        if kw.lower() in args_text:
            db_filters["city"] = kw
            break
            
    leads = database.get_leads_by_filter(db_filters)
    if not leads:
        await update.message.reply_text("❌ No matching leads found in database.")
        return
        
    excel_path = export_to_excel(leads, "Filtered", db_filters.get("city", "Export"))
    
    with open(excel_path, "rb") as f:
        await update.message.reply_document(f, filename=os.path.basename(excel_path))
        
    await update.message.reply_text(f"✅ Filter query returned {len(leads)} leads. Spreadsheet exported.")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes natural language free text message requests."""
    text = update.message.text
    matched = False
    for kw in config.INDUSTRY_KEYWORDS:
        if kw in text.lower():
            matched = True
            break
            
    if matched:
        count, industry, location, filters = parse_natural_query(text)
        context.args = [str(count), industry, location]
        if filters:
            context.args.append(filters)
        await find_handler(update, context)
    else:
        await update.message.reply_text(
            "💬 I didn't recognize any target industries in your message.\n"
            "Try specifying an industry like `dentist`, `real estate`, `salon`, etc., or use `/help`."
        )

# ===========================================================================
# MAIN RUNNER
# ===========================================================================

async def post_init(application: Application) -> None:
    """Register command suggestions list with Telegram."""
    commands = [
        ("start", "Start the bot & view command examples"),
        ("help", "Get detailed guide on commands"),
        ("find", "Run a background scraping & qualification task"),
        ("status", "View system & lead database statistics"),
        ("schedule", "Schedule a recurring search campaign"),
        ("campaigns", "List your configured campaigns"),
        ("pause", "Pause a scheduled campaign by ID"),
        ("resume", "Resume a paused campaign by ID"),
        ("export", "Export database leads to Excel"),
        ("filter", "Filter and export database leads")
    ]
    try:
        await application.bot.set_my_commands(commands)
        logger.info("Telegram Bot: Suggestion menu commands successfully set.")
    except Exception as e:
        logger.error(f"Telegram Bot: Failed to set my commands: {e}")

def run_bot():
    """Initializes and runs the Telegram bot event poll loop."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        print("[Telegram Bot Warning] TELEGRAM_BOT_TOKEN is not configured in .env. Bot is running in offline mock-mode.")
        return
        
    # Ensure tables are built
    database.init_db()
    
    app = Application.builder().token(token).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", start_handler))
    app.add_handler(CommandHandler("find", find_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("schedule", schedule_handler))
    app.add_handler(CommandHandler("campaigns", campaigns_handler))
    app.add_handler(CommandHandler("pause", pause_handler))
    app.add_handler(CommandHandler("resume", resume_handler))
    app.add_handler(CommandHandler("export", export_handler))
    app.add_handler(CommandHandler("filter", filter_handler))
    app.add_handler(MessageHandler(tg_filters.TEXT & ~tg_filters.COMMAND, text_handler))
    
    print("[Telegram Bot] Bot initialized. Starting polling loop...")
    app.run_polling()

if __name__ == "__main__":
    run_bot()

