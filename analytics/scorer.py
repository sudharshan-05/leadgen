"""
analytics/scorer.py — Lead Scorer and Opportunity Classifier.
Scores leads and generates outreach pitches.
"""
from __future__ import annotations

import re
import logging
import config
from database import save_leads_bulk

logger = logging.getLogger(__name__)

def score_single_lead(lead: dict) -> dict:
    """
    Evaluate opportunity score out of 100 for a lead.
    Categorizes the lead into HOT/WARM/COLD/SKIP.
    """
    score = 0
    
    # 1. Website exists = +20
    has_web = bool(lead.get("website") and str(lead["website"]).strip())
    is_live = lead.get("is_live", 0) == 1
    if has_web:
        score += 20
        
    # 2. Email exists = +15
    has_email = bool(lead.get("email") and str(lead["email"]).strip())
    if has_email:
        score += 15
        
    # 3. Business active = +15
    is_active = lead.get("business_active", True)
    if is_active:
        score += 15
        
    # 4. Reviews > 50 = +10
    reviews = lead.get("review_count", 0)
    try:
        rev_val = int(reviews) if reviews else 0
    except ValueError:
        rev_val = 0
    if rev_val > 50:
        score += 10
        
    # 5. Outdated website = +20
    is_outdated = lead.get("is_outdated", 0) == 1
    if is_outdated:
        score += 20
        
    # 6. No chatbot = +10
    has_chatbot = lead.get("has_chatbot", 1) == 1
    if not has_chatbot:
        score += 10
        
    # 7. No booking system = +10
    has_booking = lead.get("has_booking", 1) == 1
    if not has_booking:
        score += 10

    # 8. Extra: Has phone = +5
    has_phone = bool(lead.get("phone") and str(lead["phone"]).strip())
    if has_phone:
        score += 5

    # 9. Extra: High rating (>= 4.0) = +5
    rating = lead.get("rating", 0.0)
    try:
        r_val = float(rating) if rating else 0.0
    except ValueError:
        r_val = 0.0
    if r_val >= 4.0:
        score += 5
        
    # Subtract score if:
    # 1. Business inactive = -100
    if not is_active:
        score -= 100
        
    # 2. No contact information = -20
    if not has_phone and not has_email:
        score -= 20
        
    score = min(100, max(0, score))
    
    # Tier classification
    if score >= 80:
        tier = "HOT"
    elif score >= 70:
        tier = "WARM"
    elif score >= 50:
        tier = "COLD"
    else:
        tier = "SKIP"
        
    pitch = lead.get("outreach_angle", "")
    if not pitch:
        if not has_web or not is_live:
            pitch = "Your business has no website. Customers searching online cannot find you. We build modern websites that bring you leads 24/7."
        elif is_outdated:
            pitch = "Your website looks outdated and may be losing customers. A modern redesign can increase enquiries by 3x."
        elif not has_chatbot and not has_booking:
            pitch = "Your website has no chatbot or booking system. You're losing leads after hours. We can add an AI assistant that books appointments automatically."
        else:
            pitch = "Your digital presence is solid, but we can help scale your leads using automated outreach and advanced SEO tools."
            
    updated_lead = {**lead}
    updated_lead["opportunity_score"] = score
    updated_lead["tier"] = tier
    updated_lead["recommended_pitch"] = pitch
    
    return updated_lead

def parse_request_filters(request_text: str) -> dict:
    """Parse filter keywords from original user query text."""
    text_lower = request_text.lower()
    filters = {
        "qualified": "qualified" in text_lower,
        "high opportunity": "high opportunity" in text_lower or "high opportunity leads" in text_lower,
        "no_website": "no website" in text_lower or "without website" in text_lower,
        "outdated": "outdated" in text_lower,
        "no_chatbot": "no chatbot" in text_lower or "without chatbot" in text_lower,
        "has_email": "has email" in text_lower or "with email" in text_lower,
        "rating_above": None
    }
    
    match = re.search(r"rating above\s+(\d+(\.\d+)?)", text_lower)
    if match:
        try:
            filters["rating_above"] = float(match.group(1))
        except ValueError:
            pass
            
    return filters

def filter_leads(leads: list[dict], filters: dict) -> list[dict]:
    """Filter leads list based on parsed filter criteria."""
    filtered = []
    for lead in leads:
        score = lead.get("opportunity_score", 0)
        
        # Keep qualified leads only (opportunity_score >= 70 by default, or 60 as config)
        if score < config.MIN_SCORE_TO_QUALIFY:
            continue
            
        if filters.get("qualified") and score < config.WARM_SCORE_THRESHOLD:
            continue
        if filters.get("high opportunity") and score < config.HOT_SCORE_THRESHOLD:
            continue
        if filters.get("no_website") and (lead.get("website") and lead.get("is_live", 1) == 1):
            continue
        if filters.get("outdated") and lead.get("is_outdated", 0) == 0:
            continue
        if filters.get("no_chatbot") and lead.get("has_chatbot", 0) == 1:
            continue
        if filters.get("has_email") and lead.get("email_confidence", "none") != "found":
            continue
            
        rating = lead.get("rating", 0.0)
        try:
            r_val = float(rating) if rating else 0.0
        except ValueError:
            r_val = 0.0
            
        if filters.get("rating_above") is not None and r_val < filters["rating_above"]:
            continue
            
        filtered.append(lead)
    return filtered

def score_and_filter_leads(leads: list[dict], query_text: str = "") -> list[dict]:
    """Score a batch of leads, apply filters, and update database."""
    scored_leads = [score_single_lead(lead) for lead in leads]
    save_leads_bulk(scored_leads)
    
    if query_text:
        filters = parse_request_filters(query_text)
        print(f"[Lead Scorer] Applying request filters: {filters}")
        scored_leads = filter_leads(scored_leads, filters)
        
    return scored_leads
