"""
scrapers/justdial.py - Requests-based Justdial Scraper.
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

class JustdialScraper(BaseScraper):
    source_name = "justdial"

    def search(self, keyword: str, city: str, limit: int) -> list[dict[str, Any]]:
        print(f"[Justdial] Starting search for '{keyword} in {city}'...")
        leads = []
        
        loc_path = city.strip().replace(" ", "-").lower()
        ind_path = keyword.strip().replace(" ", "-").lower()
        
        headers = {"User-Agent": random.choice(config.USER_AGENTS)}
        page_num = 1
        retried = False
        
        while len(leads) < limit and page_num <= 5:
            url = f"https://www.justdial.com/{loc_path}/{ind_path}/page-{page_num}"
            time.sleep(random.uniform(3.0, 7.0))
            
            try:
                resp = requests.get(url, headers=headers, timeout=10)
                if resp.status_code == 403 or "blocked" in resp.text.lower():
                    if not retried:
                        print("  [Justdial] Blocked. Waiting 30 seconds to retry...")
                        time.sleep(30)
                        headers["User-Agent"] = random.choice(config.USER_AGENTS)
                        retried = True
                        continue
                    else:
                        print("  [Justdial] Still blocked. Skipping source.")
                        break
                        
                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("div.jsx-189954395, li.cntanr, div.store-details, div.result-box")
                if not cards:
                    cards = soup.find_all("div", class_="cntanr") or soup.find_all("li", class_="cntanr")
                    
                if not cards:
                    break
                    
                for card in cards:
                    if len(leads) >= limit:
                        break
                        
                    name_el = card.find("span", class_="jcn") or card.find("a", class_="store-name") or card.select_one("span.lng_cont_name")
                    if not name_el:
                        continue
                    b_name = name_el.get_text().strip()
                    
                    rating_val = 0.0
                    rating_el = card.find("span", class_="rtg") or card.select_one("span.lng_rating")
                    if rating_el:
                        try:
                            rating_val = float(rating_el.get_text().strip())
                        except ValueError:
                            pass
                            
                    review_count = 0
                    rev_el = card.find("span", class_="rt_count") or card.select_one("span.lng_reviews")
                    if rev_el:
                        try:
                            rev_text = re.sub(r"\D", "", rev_el.get_text())
                            review_count = int(rev_text) if rev_text else 0
                        except ValueError:
                            pass
                            
                    address = city
                    addr_el = card.find("span", class_="cont_fl_addr") or card.find("p", class_="address")
                    if addr_el:
                        address = addr_el.get_text().strip()
                        
                    phone = ""
                    phone_container = card.find("p", class_="contact-info") or card.find("span", class_="mobiles")
                    if phone_container:
                        phone = phone_container.get_text().strip()
                    else:
                        matches = PHONE_REGEX.findall(card.get_text())
                        if matches:
                            phone = matches[0]
                            
                    website = ""
                    web_el = card.find("a", class_="web") or card.select_one("span.web_url a")
                    if web_el and web_el.get("href"):
                        website = web_el["href"]
                        
                    category = card.find("span", class_="cat_text")
                    cat_name = category.get_text().strip() if category else keyword
                    
                    lead = {
                        "business_name": b_name,
                        "phone": phone,
                        "email": "",
                        "website": website,
                        "address": address,
                        "rating": rating_val,
                        "review_count": review_count,
                        "category": cat_name,
                        "source": "justdial",
                        "place_id": f"justdial_{abs(hash(b_name + address))}",
                        "google_maps_url": "",
                        "raw_snippet": ""
                    }
                    leads.append(self.normalize(lead, source="justdial", city=city, industry=keyword))
                    print(f"  [Justdial] Scraped: {b_name} | {phone}")
                    
                page_num += 1
                retried = False
            except Exception as e:
                logger.error(f"Error scraping Justdial: {e}")
                break
                
        return leads
