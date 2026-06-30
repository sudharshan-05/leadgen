"""
scrapers/google_search.py - Playwright-based Google Search Scraper.
"""
from __future__ import annotations

import time
import random
import logging
from urllib.parse import quote_plus, urlparse
from typing import Any

from playwright.sync_api import sync_playwright
import config
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Cache domains to avoid double indexing in same session
visited_domains: set[str] = set()
last_google_search_time = 0.0

# Compile regexes once
import re
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = re.compile(r"[\+]?[\d][\d\s\-\(\)\.]{8,20}[\d]")

def rate_limit_google_search():
    """Ensure Google is never hit more than once every 4 seconds."""
    global last_google_search_time
    now = time.time()
    elapsed = now - last_google_search_time
    if elapsed < 4.0:
        time.sleep(4.0 - elapsed)
    last_google_search_time = time.time()

class GoogleSearchScraper(BaseScraper):
    source_name = "google_search"

    def search(self, keyword: str, city: str, limit: int) -> list[dict[str, Any]]:
        print(f"[Google Search] Starting Playwright site search for '{keyword} in {city}'...")
        leads = []

        queries = [
            (f'"{keyword}" "{city}" site:instagram.com',                              "instagram"),
            (f'"{keyword}" "{city}" site:facebook.com',                               "facebook"),
            (f'"{keyword}" "{city}" site:linkedin.com/company OR site:linkedin.com/in', "linkedin"),
            (f'"{keyword} {city}" real estate builders contact phone',                 "google_search"),
        ]

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
                        ]
                    )
                    context = browser.new_context(
                        locale="en-US",
                        user_agent=random.choice(config.USER_AGENTS),
                        viewport={"width": 1280, "height": 800}
                    )
                    page = context.new_page()
                    page.set_default_timeout(30000)

                    for query, platform_source in queries:
                        if len(leads) >= limit:
                            break

                        rate_limit_google_search()
                        search_url = f"https://www.google.com/search?q={quote_plus(query)}&num=20&hl=en"
                        print(f"  [Google Search] Query: {query[:80]}...")

                        # Navigate to Google search
                        nav_ok = False
                        for attempt in range(3):
                            try:
                                page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                                time.sleep(random.uniform(2.0, 4.0))
                                nav_ok = True
                                break
                            except Exception as nav_err:
                                print(f"  [Google Search] Nav attempt {attempt+1} failed: {nav_err}")
                                time.sleep(5)

                        if not nav_ok:
                            print(f"  [Google Search] Skipping query after 3 failed navigations.")
                            continue

                        # Check for CAPTCHA
                        page_text = page.inner_text("body") if page.query_selector("body") else ""
                        if "unusual traffic" in page_text.lower() or "captcha" in page_text.lower():
                            print("  [Google Search] CAPTCHA detected — skipping remaining queries.")
                            break

                        # Collect all anchor hrefs
                        anchors = page.query_selector_all("a[href]")
                        for anchor in anchors:
                            if len(leads) >= limit:
                                break
                            try:
                                href = anchor.get_attribute("href") or ""
                                if not href.startswith("http") or "google.com" in href:
                                    continue
                                domain = urlparse(href).netloc
                                if domain in visited_domains:
                                    continue

                                # Platform filter
                                is_insta  = "instagram.com" in domain
                                is_fb     = "facebook.com" in domain
                                is_li     = "linkedin.com" in domain
                                is_social = is_insta or is_fb or is_li

                                if platform_source == "instagram" and not is_insta:
                                    continue
                                if platform_source == "facebook" and not is_fb:
                                    continue
                                if platform_source == "linkedin" and not is_li:
                                    continue
                                if platform_source == "google_search" and is_social:
                                    continue

                                visited_domains.add(domain)

                                # Title text
                                try:
                                    title = anchor.inner_text().strip()
                                except Exception:
                                    title = ""
                                if not title:
                                    try:
                                        h3 = anchor.query_selector("h3")
                                        title = h3.inner_text().strip() if h3 else href
                                    except Exception:
                                        title = href

                                b_name = title.split("-")[0].split("|")[0].strip()[:100]
                                if not b_name:
                                    b_name = domain

                                # Try to scrape the page for phone/email
                                web_phone, web_email = "", ""
                                if platform_source == "google_search":
                                    try:
                                        import requests as _req
                                        _headers = {"User-Agent": random.choice(config.USER_AGENTS)}
                                        _resp = _req.get(href, headers=_headers, timeout=8)
                                        if _resp.status_code == 200:
                                            body = _resp.text
                                            m_e = EMAIL_REGEX.search(body)
                                            if m_e:
                                                web_email = m_e.group(0)
                                            m_p = PHONE_REGEX.search(body)
                                            if m_p:
                                                web_phone = m_p.group(0)
                                    except Exception:
                                        pass

                                lead = {
                                    "business_name": b_name,
                                    "phone": web_phone,
                                    "email": web_email,
                                    "website": href,
                                    "address": city,
                                    "category": keyword,
                                    "source": platform_source,
                                    "place_id": f"gsearch_{abs(hash(href))}",
                                    "google_maps_url": "",
                                    "raw_snippet": ""
                                }
                                leads.append(self.normalize(lead, source=platform_source, city=city, industry=keyword))
                                print(f"  [Google Search] Scraped [{platform_source}]: {b_name} | {href[:60]}")
                            except Exception:
                                continue

                        time.sleep(random.uniform(3.0, 6.0))
                finally:
                    if browser:
                        browser.close()
        except Exception as e:
            logger.exception(f"Google Search Playwright scraper failed: {e}")
            print(f"  [Google Search Error] {e}")")

        return leads
