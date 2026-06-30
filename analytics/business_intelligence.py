"""
analytics/business_intelligence.py — Layer 4: Business Intelligence Extractor.
Analyzes scraped page content and lead metadata to extract business profiles.
"""
from __future__ import annotations

import re
import json
import logging
from concurrent.futures import ThreadPoolExecutor
import requests

import config

logger = logging.getLogger(__name__)

# Industry keyword map
INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "Real Estate": [
        "real estate", "property", "plot", "villa", "apartment", "flat", "builder",
        "construction", "land", "housing", "promoter", "realty", "realtor", "realtors",
        "home", "house", "bungalow", "residential", "commercial", "lease", "rent"
    ],
    "Healthcare": [
        "hospital", "clinic", "doctor", "dental", "dentist", "pharmacy", "medical",
        "health", "care", "ortho", "pediatric", "gynec", "diagnostic", "lab", "pathology",
        "eye care", "vision", "skin", "derma", "ayurveda", "yoga"
    ],
    "Restaurant & Food": [
        "restaurant", "hotel", "cafe", "food", "biryani", "catering", "kitchen", "bakery",
        "sweet", "mess", "dhaba", "eatery", "pizza", "burger", "tiffin", "canteen"
    ],
    "Education": [
        "school", "college", "institute", "academy", "coaching", "tuition", "training",
        "education", "learning", "study", "university", "course", "classes"
    ],
    "Retail & Shopping": [
        "store", "shop", "boutique", "mart", "supermarket", "showroom", "mall",
        "garment", "textile", "jewelry", "mobile", "electronics", "hardware"
    ],
    "Automobile": [
        "car", "automobile", "vehicle", "two wheeler", "bike", "scooter", "auto",
        "garage", "service center", "mechanic", "spare parts", "showroom"
    ],
    "Salon & Beauty": [
        "salon", "beauty", "spa", "hair", "skin care", "parlour", "makeup",
        "grooming", "unisex", "barber"
    ],
    "Finance": [
        "bank", "finance", "loan", "insurance", "investment", "mutual fund", "tax",
        "ca", "chartered accountant", "accounting", "audit", "gst", "nri"
    ],
    "IT & Technology": [
        "software", "it", "technology", "digital", "web", "app", "solution",
        "developer", "cyber", "cloud", "erp", "crm", "startup"
    ],
    "Legal": [
        "advocate", "lawyer", "legal", "law", "attorney", "court", "notary"
    ],
}

SERVICE_SECTION_TAGS = ["h1", "h2", "h3", "li", "strong", "b"]

def _fetch_page_html(url: str) -> tuple[str, str]:
    """Return (html, final_url). Returns ('', '') on failure."""
    if not url:
        return "", ""
    target = url.strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    try:
        resp = requests.get(
            target,
            headers={"User-Agent": config.USER_AGENTS[0]},
            timeout=config.WEBSITE_TIMEOUT,
            allow_redirects=True
        )
        if resp.status_code < 400:
            return resp.text, resp.url
    except Exception:
        pass
    return "", ""


def _detect_industry(lead: dict, body_text: str) -> str:
    """Detect the most likely industry from category + page text."""
    category = (lead.get("category") or "").lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw in category for kw in keywords):
            return industry

    body_lower = body_text.lower()
    best_industry = "General Business"
    best_hits = 0
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in body_lower)
        if hits > best_hits:
            best_hits = hits
            best_industry = industry

    return best_industry


def _extract_services(soup) -> list[str]:
    """Extract a clean list of services from heading and list tags."""
    services = []
    seen = set()
    skip_words = {"home", "about", "contact", "gallery", "blog", "news", "faq", "menu", "login", "register"}

    for tag in soup.find_all(SERVICE_SECTION_TAGS):
        text = tag.get_text(separator=" ").strip()
        text_clean = re.sub(r"\s+", " ", text)

        if 5 <= len(text_clean) <= 80:
            lower = text_clean.lower()
            if lower not in seen and not any(sw == lower for sw in skip_words):
                seen.add(lower)
                services.append(text_clean)

        if len(services) >= 10:
            break

    return services[:8]


def _estimate_location_count(body_text: str) -> int:
    """Estimate number of locations from body text."""
    body_lower = body_text.lower()
    patterns = [
        r"(\d+)\s+(?:branch(?:es)?|outlet(?:s)?|location(?:s)?|office(?:s)?|showroom(?:s)?|center(?:s)?)",
        r"(?:branch(?:es)?|outlet(?:s)?|location(?:s)?)\s+(?:in|at|across)\s+(\d+)",
    ]
    for pat in patterns:
        m = re.search(pat, body_lower)
        if m:
            try:
                return max(1, int(m.group(1)))
            except (IndexError, ValueError):
                pass

    multi_hints = ["branches", "outlets", "multiple locations", "pan india", "all over tamilnadu"]
    if any(h in body_lower for h in multi_hints):
        return 3

    return 1


def _estimate_company_size(lead: dict, location_count: int) -> str:
    """
    micro  : < 5 reviews, 1 location, no website
    small  : 5–50 reviews, 1–2 locations
    medium : 51–200 reviews, OR 3+ locations
    large  : 200+ reviews, OR known brand signals
    """
    reviews = 0
    try:
        reviews = int(lead.get("review_count") or 0)
    except (ValueError, TypeError):
        reviews = 0

    if reviews >= 200 or location_count >= 5:
        return "large"
    elif reviews >= 51 or location_count >= 3:
        return "medium"
    elif reviews >= 5 or location_count >= 2:
        return "small"
    else:
        return "micro"


def _estimate_budget_level(company_size: str, rating: float, reviews: int) -> str:
    """
    low    : micro company, low reviews/rating
    medium : small/medium company
    high   : large company, high rating+reviews
    """
    if company_size in ("large",) or (rating >= 4.5 and reviews >= 100):
        return "high"
    elif company_size in ("medium", "small") or reviews >= 20:
        return "medium"
    else:
        return "low"


def _build_summary(lead: dict, page_title: str, meta_desc: str, industry: str, services: list[str]) -> str:
    """Build a 1–2 sentence company summary."""
    name = lead.get("business_name") or "This business"
    location = lead.get("address") or lead.get("city") or "the local area"

    if meta_desc and len(meta_desc) > 30:
        return meta_desc[:300].strip()

    if page_title and len(page_title) > 10:
        base = f"{name} is a {industry} business in {location}."
        if services:
            base += f" Services include: {', '.join(services[:3])}."
        return base

    return f"{name} operates in the {industry} sector in {location}."


def analyze_business(lead: dict) -> dict:
    """
    Run business intelligence analysis on a single lead.
    Fetches website HTML (if available) and extracts structured insights.
    """
    from bs4 import BeautifulSoup

    enriched = {**lead}
    website = (lead.get("website") or "").strip()

    html, final_url = _fetch_page_html(website) if website else ("", "")

    soup = BeautifulSoup(html, "html.parser") if html else None
    body_text = soup.get_text(separator=" ") if soup else ""

    page_title = ""
    meta_desc = ""
    if soup:
        title_el = soup.find("title")
        if title_el:
            page_title = title_el.get_text().strip()[:200]
        meta_el = soup.find("meta", attrs={"name": "description"})
        if meta_el:
            meta_desc = meta_el.get("content", "").strip()[:500]

    industry = _detect_industry(lead, body_text)
    services = _extract_services(soup) if soup else []
    location_count = _estimate_location_count(body_text)

    rating = 0.0
    try:
        rating = float(lead.get("rating") or 0)
    except (ValueError, TypeError):
        rating = 0.0

    reviews = 0
    try:
        reviews = int(lead.get("review_count") or 0)
    except (ValueError, TypeError):
        reviews = 0

    company_size = _estimate_company_size(lead, location_count)
    budget_level = _estimate_budget_level(company_size, rating, reviews)
    summary = _build_summary(lead, page_title, meta_desc, industry, services)

    enriched["company_summary"]    = summary
    enriched["industry_detected"]  = industry
    enriched["services_list"]      = json.dumps(services, ensure_ascii=False)
    enriched["location_count"]     = location_count
    enriched["company_size"]       = company_size
    enriched["budget_level"]       = budget_level

    print(f"  [BizIntel] {lead.get('business_name','?')[:35]} → {industry} | {company_size} | budget={budget_level}")
    return enriched


def analyze_business_batch(leads: list[dict]) -> list[dict]:
    """Run business intelligence on all leads in parallel."""
    print("=" * 70)
    print(f"[Layer 4] BUSINESS INTELLIGENCE — {len(leads)} leads")
    print("=" * 70)

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=config.WEBSITE_ANALYSER_WORKERS) as executor:
        futures = {executor.submit(analyze_business, lead): lead for lead in leads}
        for fut in futures:
            try:
                results.append(fut.result())
            except Exception as e:
                original = futures[fut]
                logger.error(f"BizIntel failed for {original.get('business_name')}: {e}")
                original.setdefault("company_summary", "")
                original.setdefault("industry_detected", "General Business")
                original.setdefault("services_list", "[]")
                original.setdefault("location_count", 1)
                original.setdefault("company_size", "micro")
                original.setdefault("budget_level", "low")
                results.append(original)

    print(f"[BizIntel] Business intelligence complete for {len(results)} leads.")
    return results
