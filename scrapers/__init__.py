"""
scrapers package initialization.
Exports all scrapers and the parallel runner.
"""
from __future__ import annotations

from scrapers.base_scraper import BaseScraper, LEAD_SCHEMA
from scrapers.google_maps import GoogleMapsScraper
from scrapers.google_search import GoogleSearchScraper
from scrapers.justdial import JustdialScraper
from scrapers.sulekha import SulekhaScraper
from scrapers.orchestrator import run_scrapers_parallel, validate_lead_quality

__all__ = [
    "BaseScraper",
    "LEAD_SCHEMA",
    "GoogleMapsScraper",
    "GoogleSearchScraper",
    "JustdialScraper",
    "SulekhaScraper",
    "run_scrapers_parallel",
    "validate_lead_quality"
]
