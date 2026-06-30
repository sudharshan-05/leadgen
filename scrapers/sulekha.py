"""
scrapers/sulekha.py - Requests-based Sulekha Scraper.
"""
from __future__ import annotations

import re
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from typing import Any

import config
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"[\+]?[\d][\d\s\-\(\)\.]{8,20}[\d]")

class SulekhaScraper(BaseScraper):
    source_name = "sulekha"

    def search(self, keyword: str, city: str, limit: int) -> list[dict[str, Any]]:
        print(f"[Sulekha] Starting search for '{keyword} in {city}'...")
        leads = []
        
        loc_path = city.strip().replace(" ", "-").lower()
        ind_path = keyword.strip().replace(" ", "-").lower()
        
        headers = {"User-Agent": random.choice(config.USER_AGENTS)}
        url = f"https://www.sulekha.com/{ind_path}/{loc_path}"
        
        try:
            time.sleep(random.uniform(3.0, 7.0))
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 403 or "blocked" in resp.text.lower():
                print("  [Sulekha] Blocked. Retrying once after 30 seconds...")
                time.sleep(30)
                headers["User-Agent"] = random.choice(config.USER_AGENTS)
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    print("  [Sulekha] Still blocked. Skipping source.")
                    return leads
                    
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select("div.card, li.listing-item, div.business-listing")
            if not cards:
                cards = soup.find_all("div", class_="card")
                
            for card in cards:
                if len(leads) >= limit:
                    break
                    
                name_el = card.find("h3") or card.find("a", class_="name")
                if not name_el:
                    continue
                b_name = name_el.get_text().strip()
                
                phone = ""
                phone_el = card.find("a", class_="phone") or card.find("span", class_="contact-number")
                if phone_el:
                    phone = phone_el.get_text().strip()
                else:
                    matches = PHONE_REGEX.findall(card.get_text())
                    if matches:
                        phone = matches[0]
                        
                rating_val = 0.0
                rating_el = card.find("span", class_="rating-value") or card.find("span", class_="stars")
                if rating_el:
                    try:
                        rating_val = float(re.search(r"(\d+\.?\d*)", rating_el.get_text()).group(1))
                    except Exception:
                        pass
                        
                review_count = 0
                rev_el = card.find("span", class_="review-count") or card.find("span", class_="reviews")
                if rev_el:
                    try:
                        review_count = int(re.search(r"(\d+)", rev_el.get_text()).group(1))
                    except Exception:
                        pass
                        
                address = city
                addr_el = card.find("span", class_="address") or card.find("p", class_="location")
                if addr_el:
                    address = addr_el.get_text().strip()
                    
                website = ""
                web_el = card.find("a", class_="website") or card.find("a", href=True)
                if web_el and web_el.get("href") and web_el["href"].startswith("http"):
                    website = web_el["href"]
                    
                lead = {
                    "business_name": b_name,
                    "phone": phone,
                    "email": "",
                    "website": website,
                    "address": address,
                    "rating": rating_val,
                    "review_count": review_count,
                    "category": keyword,
                    "source": "sulekha",
                    "place_id": f"sulekha_{abs(hash(b_name + address))}",
                    "google_maps_url": "",
                    "raw_snippet": ""
                }
                leads.append(self.normalize(lead, source="sulekha", city=city, industry=keyword))
                print(f"  [Sulekha] Scraped: {b_name} | {phone}")
                
        except Exception as e:
            logger.error(f"Error scraping Sulekha: {e}")
            
        return leads
