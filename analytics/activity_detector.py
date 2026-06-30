"""
analytics/activity_detector.py — Layer 1: Activity Detection.
Determines whether a business is actively operating by checking website live/DNS status, etc.
"""
from __future__ import annotations

import ssl
import socket
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
import requests

import config

logger = logging.getLogger(__name__)

CURRENT_YEAR = 2026
ACTIVE_YEAR_THRESHOLD = 2022   # copyright year must be >= this to be "active"
MIN_ACTIVITY_SCORE = 30        # below this → business_active = False (reject)

def _check_dns(hostname: str) -> bool:
    """Return True if hostname resolves via DNS."""
    try:
        socket.setdefaulttimeout(5)
        socket.gethostbyname(hostname)
        return True
    except Exception:
        return False


def _check_ssl(hostname: str) -> bool:
    """Return True if a valid SSL certificate is found on port 443."""
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(
            socket.create_connection((hostname, 443), timeout=6),
            server_hostname=hostname
        ) as ssock:
            cert = ssock.getpeercert()
            return bool(cert)
    except Exception:
        return False


def _check_website_live(url: str) -> tuple[bool, float]:
    """
    Return (is_live, load_time) for the given URL.
    is_live = True if HTTP status < 400.
    """
    if not url:
        return False, 0.0
    target = url.strip()
    if not target.startswith(("http://", "https://")):
        target = "https://" + target
    try:
        start = time.time()
        resp = requests.get(
            target,
            headers={"User-Agent": config.USER_AGENTS[0]},
            timeout=config.WEBSITE_TIMEOUT,
            allow_redirects=True
        )
        elapsed = time.time() - start
        return resp.status_code < 400, round(elapsed, 3)
    except Exception:
        return False, 0.0


def _extract_copyright_year(html: str) -> int:
    """Find the most recent 4-digit year in page HTML."""
    import re
    years = re.findall(r"\b(20\d{2})\b", html)
    if years:
        return max(int(y) for y in years)
    return 0


def detect_activity(lead: dict) -> dict:
    """
    Run all activity checks on a single lead.
    Returns the lead dict enriched with:
        business_active (bool)
        activity_score  (int 0-100)
    """
    score = 0
    details: list[str] = []

    website = (lead.get("website") or "").strip()
    hostname = ""
    html_body = ""

    # ── 1. DNS resolution (15 pts) ────────────────────────────────────────
    if website:
        try:
            parsed = urlparse(website if website.startswith("http") else "https://" + website)
            hostname = parsed.hostname or ""
        except Exception:
            hostname = ""

        if hostname and _check_dns(hostname):
            score += 15
            details.append("DNS OK")
        else:
            details.append("DNS FAIL")
    else:
        score += 5
        details.append("No website")

    # ── 2. Website live check (20 pts) ────────────────────────────────────
    if website:
        is_live, load_time = _check_website_live(website)
        if is_live:
            score += 20
            details.append("Website LIVE")
            try:
                resp = requests.get(
                    website if website.startswith("http") else "https://" + website,
                    headers={"User-Agent": config.USER_AGENTS[0]},
                    timeout=8,
                    allow_redirects=True
                )
                html_body = resp.text
            except Exception:
                html_body = ""
        else:
            details.append("Website DEAD")

    # ── 3. SSL certificate valid (10 pts) ────────────────────────────────
    if hostname and website and "https" in website.lower():
        if _check_ssl(hostname):
            score += 10
            details.append("SSL valid")
        else:
            details.append("SSL invalid")

    # ── 4. Recent copyright year (15 pts) ────────────────────────────────
    if html_body:
        year = _extract_copyright_year(html_body)
        if year >= ACTIVE_YEAR_THRESHOLD:
            score += 15
            details.append(f"Recent copyright {year}")
        elif year > 0:
            details.append(f"Old copyright {year}")
        else:
            details.append("No copyright year")

    # ── 5. Has phone or email (15 pts each, max 20) ───────────────────────
    contact_score = 0
    if lead.get("phone") and str(lead["phone"]).strip():
        contact_score += 10
        details.append("Has phone")
    if lead.get("email") and str(lead["email"]).strip():
        contact_score += 10
        details.append("Has email")
    score += min(contact_score, 20)

    # ── 6. Reviews signal (20 pts) ────────────────────────────────────────
    reviews = 0
    try:
        reviews = int(lead.get("review_count") or 0)
    except (ValueError, TypeError):
        reviews = 0

    if reviews >= 100:
        score += 20
        details.append(f"High reviews ({reviews})")
    elif reviews >= 20:
        score += 12
        details.append(f"Moderate reviews ({reviews})")
    elif reviews >= 5:
        score += 6
        details.append(f"Few reviews ({reviews})")
    else:
        details.append("No/few reviews")

    # Clamp
    activity_score = min(100, max(0, score))
    business_active = activity_score >= MIN_ACTIVITY_SCORE

    enriched = {**lead}
    enriched["activity_score"] = activity_score
    enriched["business_active"] = business_active
    enriched["activity_details"] = "; ".join(details)

    status_icon = "✅" if business_active else "❌"
    print(f"  [Activity] {status_icon} {lead.get('business_name', 'Unknown')[:40]} | score={activity_score} | {', '.join(details[:3])}")

    return enriched


def detect_activity_batch(leads: list[dict], reject_inactive: bool = True) -> list[dict]:
    """
    Run activity detection on all leads in parallel.
    If reject_inactive=True, drops leads where business_active=False.
    """
    print("=" * 70)
    print(f"[Layer 1] ACTIVITY DETECTION — {len(leads)} leads")
    print("=" * 70)

    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=config.WEBSITE_ANALYSER_WORKERS) as executor:
        futures = {executor.submit(detect_activity, lead): lead for lead in leads}
        for fut in futures:
            try:
                results.append(fut.result())
            except Exception as e:
                original = futures[fut]
                logger.error(f"Activity detection failed for {original.get('business_name')}: {e}")
                original["activity_score"] = 0
                original["business_active"] = False
                original["activity_details"] = f"Error: {e}"
                results.append(original)

    active_count = sum(1 for r in results if r.get("business_active"))
    rejected_count = len(results) - active_count
    print(f"\n[Activity] Active: {active_count} | Rejected (inactive): {rejected_count}")

    if reject_inactive:
        results = [r for r in results if r.get("business_active", False)]
        print(f"[Activity] Kept {len(results)} active leads for next pipeline stage.")

    return results
