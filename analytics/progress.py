"""
analytics/progress.py — Real-time progress reporting helper.
Tracks workflow progress and sends periodic updates to Telegram.
"""
from __future__ import annotations

import time
import requests
import logging
import config

logger = logging.getLogger(__name__)

def send_telegram_update(chat_id: str | int | None, text: str) -> bool:
    """Send a text message directly to a Telegram chat using requests."""
    if not chat_id or not config.TELEGRAM_BOT_TOKEN:
        return False
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": str(chat_id), "text": text}
        resp = requests.post(url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send Telegram update: {e}")
        return False

class ProgressReporter:
    def __init__(self, telegram_chat_id: str | int | None, total_steps: int):
        self.chat_id = telegram_chat_id
        self.total = total_steps
        self.current = 0
        self.start_time = time.time()
        
    def update(self, message: str) -> None:
        self.current += 1
        elapsed = round(time.time() - self.start_time)
        print(f"[{self.current}/{self.total}] {message} ({elapsed}s)")
        if self.current % 10 == 0:
            send_telegram_update(
                self.chat_id, 
                f"Progress: {self.current}/{self.total}\n{message}"
            )
            
    def done(self, summary: str) -> None:
        total_time = round(time.time() - self.start_time)
        print(f"Done in {total_time}s")
        send_telegram_update(self.chat_id, summary)
