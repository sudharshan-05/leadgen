"""
scrapers/orchestrator.py - Orchestrates parallel execution of scrapers.
"""
from __future__ import annotations

import re
import logging
from concurrent.futures import ThreadPoolExecutor
import config

from scrapers.google_maps import GoogleMapsScraper
from scrapers.google_search import GoogleSearchScraper
from scrapers.justdial import JustdialScraper
from scrapers.sulekha import SulekhaScraper
from analytics.dedup import deduplicate_leads

logger = logging.getLogger(__name__)

# Keywords that identify non-business listings (houses, personal properties, etc.)
_NON_BUSINESS_KEYWORDS = [
    "house", "home", "flat", "kuppam", "illam", "veedu", "room",
    "layout", "colony", "nagar layout", "tn home", "tamilnadu home",
    "br illam", "jk home", "rr kuppam", "rs home", "lok home",
    "lokesh house", "farook house", "jothi home", "sk illam"
]

# Junk placeholder patterns scraped from Google Maps area labels
_JUNK_PATTERNS = [
    r"^\s*$",                          # Completely empty
    r"^[\W\d]+$",                     # Only symbols/numbers
    r"^.{1,2}$",                      # Too short (1-2 chars)
]
_JUNK_RE = [re.compile(p) for p in _JUNK_PATTERNS]

def validate_lead_quality(lead: dict) -> bool:
    """
    Returns True if the lead passes minimum quality standards.
    """
    name = (lead.get("business_name") or "").strip()

    if not name or len(name) < 3:
        return False

    for pat in _JUNK_RE:
        if pat.match(name):
            return False

    name_lower = name.lower()
    if any(kw in name_lower for kw in _NON_BUSINESS_KEYWORDS):
        return False

    has_phone   = bool(lead.get("phone") and str(lead["phone"]).strip())
    has_email   = bool(lead.get("email") and str(lead["email"]).strip())
    has_website = bool(lead.get("website") and str(lead["website"]).strip())
    has_maps    = bool(lead.get("google_maps_url") and str(lead["google_maps_url"]).strip())
    has_place   = bool(lead.get("place_id") and str(lead["place_id"]).strip())

    if not (has_phone or has_email or has_website or has_maps or has_place):
        return False

    return True

def run_scrapers_parallel(industry: str, location: str, limit: int) -> list[dict]:
    """Run all 4 scrapers concurrently, merge outputs, and filter via deduplicator."""
    print("=" * 70)
    print(f"Starting Multi-Source Scraper for '{industry}' in '{location}' (Limit: {limit} per source)...")
    print("=" * 70)
    
    raw_leads = []
    
    # Thread workers execution mapping
    with ThreadPoolExecutor(max_workers=config.SCRAPER_WORKERS) as executor:
        futures = {
            executor.submit(GoogleMapsScraper().search, industry, location, limit): "google_maps",
            executor.submit(GoogleSearchScraper().search, industry, location, limit): "google_search",
            executor.submit(JustdialScraper().search, industry, location, limit): "justdial",
            executor.submit(SulekhaScraper().search, industry, location, limit): "sulekha"
        }
        
        for fut in futures:
            source = futures[fut]
            try:
                leads_batch = fut.result()
                raw_leads.extend(leads_batch)
                print(f"[Scraper] {source} complete. Scraped {len(leads_batch)} raw leads.")
            except Exception as e:
                logger.exception(f"Source Scraper '{source}' crashed during parallel run")
                print(f"[Scraper Error] Source '{source}' crashed: {e}")
                
    # Deduplicate merged list using dedup engine
    print("\nMerging and deduplicating leads list...")
    unique_leads = deduplicate_leads(raw_leads, skip_db_check=True)

    # Quality Gate
    before_qc = len(unique_leads)
    unique_leads = [l for l in unique_leads if validate_lead_quality(l)]
    rejected_qc = before_qc - len(unique_leads)
    if rejected_qc > 0:
        print(f"[Quality Gate] Rejected {rejected_qc} low-quality leads. Kept {len(unique_leads)} valid leads.")

    return unique_leads
