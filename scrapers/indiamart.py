"""
indiamart.py — IndiaMart scraper (production stub, schema-compliant).
"""
from __future__ import annotations

import logging
from typing import Any

from .base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class IndiaMartScraper(BaseScraper):
    """IndiaMart B2B marketplace scraper."""

    source_name: str = "indiamart"

    def __init__(self, headless: bool = False) -> None:
        self.headless = headless

    def search(self, keyword: str, city: str, limit: int) -> list[dict[str, Any]]:
        if not keyword or not city:
            raise ValueError("keyword and city are required")
        if limit <= 0:
            raise ValueError("limit must be a positive integer")

        logger.info(
            "[IndiaMart] Starting search — keyword=%s city=%s limit=%d",
            keyword, city, limit,
        )

        leads: list[dict[str, Any]] = []

        # TODO: Replace with real Playwright scraping
        for index in range(min(limit, 0)):          # yields 0 rows until implemented
            raw = {
                "business_name": f"IndiaMart {keyword} {index + 1}",
                "website":       "",
                "phone":         "",
                "address":       city,
                "rating":        "",
                "reviews":       "",
                "industry":      keyword,
            }
            leads.append(
                self.normalize(raw, source=self.source_name, city=city, industry=keyword)
            )

        logger.info("[IndiaMart] Completed — %d leads returned", len(leads))
        return leads
