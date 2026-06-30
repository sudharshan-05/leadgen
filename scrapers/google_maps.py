"""
scrapers/google_maps.py - Playwright-based Google Maps Scraper.
"""
from __future__ import annotations

import re
import time
import random
import logging
from urllib.parse import quote_plus
from typing import Any

from playwright.sync_api import sync_playwright
import config
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class GoogleMapsScraper(BaseScraper):
    source_name = "google_maps"

    def search(self, keyword: str, city: str, limit: int) -> list[dict[str, Any]]:
        print(f"[Google Maps] Starting search for '{keyword} in {city}'...")
        leads = []
        query = f"{keyword} {city}"
        search_url = f"https://www.google.com/maps/search/{quote_plus(query)}"
        
        try:
            with sync_playwright() as pw:
                browser = None
                try:
                    browser = pw.chromium.launch(
                        headless=True,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--no-sandbox",
                            "--disable-http2",
                            "--disable-quic"
                        ]
                    )
                    context = browser.new_context(
                        locale="en-US",
                        user_agent=random.choice(config.USER_AGENTS)
                    )
                    page = context.new_page()
                    page.set_default_timeout(45000)
                    
                    # Navigate to search URL with retry
                    search_success = False
                    for attempt in range(3):
                        try:
                            page.goto(search_url, wait_until="domcontentloaded")
                            search_success = True
                            break
                        except Exception as e:
                            if attempt < 2:
                                print(f"  [Google Maps] Search page load failed, retrying in 5s... ({e})")
                                time.sleep(5)
                            else:
                                raise e
                    
                    # Dismiss cookie consent if it appears
                    for btn_text in ["I agree", "Accept all", "Accept"]:
                        try:
                            btn = page.locator(f"button:has-text('{btn_text}')").first
                            if btn.is_visible(timeout=2000):
                                btn.click()
                                time.sleep(1)
                        except Exception:
                            pass
                    
                    # Scroll results panel
                    feed_selector = "div[role='feed']"
                    try:
                        page.locator(feed_selector).wait_for(state="visible", timeout=15000)
                    except Exception:
                        pass
                    
                    target_count = limit * 3
                    prev_count = 0
                    for scroll_attempt in range(15):
                        current = page.locator("a[href*='/place/']").count()
                        if current >= target_count:
                            break
                        page.evaluate(
                            f"const el = document.querySelector(\"{feed_selector}\"); if(el) el.scrollBy(0, el.scrollHeight);"
                        )
                        time.sleep(1.5)
                        new_count = page.locator("a[href*='/place/']").count()
                        if new_count == prev_count:
                            break
                        prev_count = new_count
                        
                    # Collect cards
                    cards = []
                    anchors = page.locator("a[href*='/place/']")
                    total_cards = anchors.count()
                    
                    for idx in range(total_cards):
                        if len(cards) >= target_count:
                            break
                        try:
                            anchor = anchors.nth(idx)
                            href = anchor.get_attribute("href") or ""
                            if "/place/" not in href:
                                continue
                            
                            name = ""
                            try:
                                heading = anchor.locator("div[role='heading']").first
                                if heading.count():
                                    name = heading.inner_text().strip()
                            except Exception:
                                name = "Google Maps Lead"
                                
                            cards.append((href, name))
                        except Exception:
                            continue
                    
                    # Navigate details URLs
                    for place_href, place_name in cards:
                        if len(leads) >= limit:
                            break
                        
                        time.sleep(random.uniform(1.0, 2.5))
                        
                        try:
                            max_nav_retries = 2
                            nav_success = False
                            for nav_attempt in range(max_nav_retries):
                                try:
                                    page.goto(place_href, wait_until="domcontentloaded")
                                    page.wait_for_timeout(2000)
                                    nav_success = True
                                    break
                                except Exception as nav_e:
                                    if nav_attempt < max_nav_retries - 1:
                                        print(f"  [Google Maps] Detail navigation failed, retrying in 5s... ({nav_e})")
                                        time.sleep(5)
                                    else:
                                        raise nav_e
                            
                            if not nav_success:
                                continue
                            
                            # Detail panel
                            panel_selector = "div[role='main'][aria-label]"
                            panel = page.locator(panel_selector).first
                            if not panel.count():
                                panel = page.locator("div[role='main']").first
                                
                            # Extract fields
                            b_name = place_name
                            try:
                                h1 = panel.locator("h1").first
                                if h1.count() and h1.is_visible():
                                    b_name = h1.inner_text().strip()
                            except Exception:
                                pass
                                
                            # Phone
                            phone_num = ""
                            try:
                                p_btn = panel.locator("button[data-item-id^='phone:tel:']").first
                                if p_btn.count():
                                    phone_num = p_btn.get_attribute("data-item-id").split("phone:tel:")[-1].strip()
                            except Exception:
                                pass
                                
                            # Website
                            web_url = ""
                            try:
                                w_btn = panel.locator("a[data-item-id='authority']").first
                                if w_btn.count():
                                    web_url = w_btn.get_attribute("href") or ""
                            except Exception:
                                pass
                                
                            # Rating
                            rating_val = 0.0
                            try:
                                r_span = panel.locator("span[aria-label*='stars']").first
                                if r_span.count():
                                    aria_label = r_span.get_attribute("aria-label")
                                    r_match = re.search(r"(\d+\.?\d*)", aria_label)
                                    if r_match:
                                        rating_val = float(r_match.group(1))
                            except Exception:
                                pass
                                
                            # Reviews
                            reviews_count = 0
                            try:
                                rev_span = panel.locator("span[aria-label*='reviews']").first
                                if rev_span.count():
                                    aria_label = rev_span.get_attribute("aria-label")
                                    rev_match = re.search(r"([\d,]+)", aria_label)
                                    if rev_match:
                                        reviews_count = int(rev_match.group(1).replace(",", ""))
                            except Exception:
                                pass
                                
                            # Address
                            addr = ""
                            try:
                                addr_btn = panel.locator("button[data-item-id='address']").first
                                if addr_btn.count():
                                    addr = addr_btn.inner_text().strip()
                            except Exception:
                                pass
                            
                            # Extract place_id
                            place_id = ""
                            p_match = re.search(r'!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)', page.url)
                            if p_match:
                                place_id = p_match.group(1)
                            else:
                                place_id = f"gmaps_{hash(page.url)}"
                                
                            lead = {
                                "business_name": b_name,
                                "phone": phone_num,
                                "website": web_url,
                                "address": addr,
                                "rating": rating_val,
                                "review_count": reviews_count,
                                "category": keyword,
                                "source": "google_maps",
                                "place_id": place_id,
                                "google_maps_url": page.url,
                                "raw_snippet": ""
                            }
                            
                            leads.append(self.normalize(lead, source="google_maps", city=city, industry=keyword))
                            print(f"  [Google Maps] Scraped: {b_name} | {phone_num}")
                        except Exception as e:
                            logger.error(f"Error scraping maps details page: {e}")
                            continue
                finally:
                    if browser:
                        browser.close()
        except Exception as e:
            logger.exception("Google Maps scraping failed")
            print(f"  [Google Maps Error] Failed: {e}")
            
        return leads
