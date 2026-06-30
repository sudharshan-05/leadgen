"""
base_scraper.py — Abstract base class for all scrapers.

Defines:
  - LEAD_SCHEMA: the canonical lead dictionary every scraper must produce.
  - BaseScraper.search(): abstract method each scraper implements.
  - BaseScraper.normalize(): converts a raw scraper dict to LEAD_SCHEMA.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Canonical lead schema
# Every scraper MUST return dicts matching these keys.
# Missing keys are filled with "" by normalize().
# ---------------------------------------------------------------------------
LEAD_SCHEMA: dict[str, Any] = {
    "business_name": "",
    "phone":          "",
    "email":          "",
    "website":        "",
    "address":        "",
    "city":           "",
    "rating":         0.0,
    "review_count":   0,
    "category":       "",
    "source":         "",
    "place_id":       "",
    "google_maps_url": "",
    "raw_snippet":    "",
    "scraped_at":     "",
}


class BaseScraper(ABC):
    """Abstract scraper interface.  All concrete scrapers inherit this."""

    # Subclasses set this to their source identifier, e.g. "google_maps"
    source_name: str = ""

    @abstractmethod
    def search(self, keyword: str, city: str, limit: int) -> list[dict[str, Any]]:
        """
        Run a source-specific search and return a list of lead dicts.

        Every returned dict SHOULD contain the keys from LEAD_SCHEMA.
        Call self.normalize() before returning to guarantee compliance.
        """
        raise NotImplementedError

    def normalize(
        self,
        raw: dict[str, Any],
        *,
        source:   str = "",
        city:     str = "",
        industry: str = "",
    ) -> dict[str, Any]:
        """
        Normalize a raw scraper dict to exactly match LEAD_SCHEMA.
        """
        lead: dict[str, Any] = LEAD_SCHEMA.copy()

        # Copy recognised fields from raw dict
        for key in LEAD_SCHEMA:
            val = raw.get(key, None)
            if val is not None:
                if key == "rating":
                    try:
                        lead[key] = float(val)
                    except ValueError:
                        lead[key] = 0.0
                elif key == "review_count":
                    try:
                        lead[key] = int(val)
                    except ValueError:
                        lead[key] = 0
                else:
                    lead[key] = str(val).strip()

        # Apply overrides
        lead["source"]     = source or self.source_name or lead["source"] or ""
        lead["city"]       = city or lead["city"] or ""
        lead["category"]   = industry or lead["category"] or ""
        lead["scraped_at"] = datetime.utcnow().isoformat()

        return lead
