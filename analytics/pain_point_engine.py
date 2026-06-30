"""
analytics/pain_point_engine.py — Layers 5, 6, 7: Pain Point Detection, Service Recommendation,
and Outreach Angle Generation.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

def detect_pain_points(lead: dict) -> list[str]:
    """
    Inspect lead attributes and return a list of human-readable pain points.
    Each pain point clearly states the problem and its business impact.
    """
    pain_points: list[str] = []

    has_web  = bool(lead.get("website") and str(lead.get("website", "")).strip())
    is_live  = lead.get("is_live", 0) == 1
    is_dead  = has_web and not is_live

    # Presence issues
    if not has_web:
        pain_points.append("Zero online presence — invisible to Google searches and online buyers")
    elif is_dead:
        pain_points.append("Website is unreachable — 100% of online traffic is being lost")
    elif lead.get("is_outdated", 0) == 1:
        pain_points.append("Outdated website — losing credibility and modern buyers")
    elif lead.get("is_mobile_ready", 1) == 0:
        pain_points.append("Not mobile-friendly — 70%+ of Indian users browse on phones")

    # Speed
    speed = lead.get("page_speed_score", 100)
    try:
        speed = int(speed) if speed else 100
    except (ValueError, TypeError):
        speed = 100
    if speed < 40:
        pain_points.append("Critically slow website — 53% of users leave pages that load in >3 seconds")
    elif speed < 70:
        pain_points.append("Slow website — poor page speed hurts Google ranking and user experience")

    # Security
    if has_web and is_live and lead.get("has_https", 1) == 0:
        pain_points.append("No HTTPS — browsers warn visitors 'Not Secure', damaging trust")

    # Missing tools
    if lead.get("has_chatbot", 1) == 0:
        pain_points.append("No AI chatbot — missing after-hours leads and instant customer queries")
    if lead.get("has_booking", 1) == 0:
        pain_points.append("No online appointment/booking system — customers still calling manually")
    if lead.get("has_whatsapp", 1) == 0:
        pain_points.append("No WhatsApp integration — missing the #1 communication channel in India")

    # Lead capture and content
    if has_web and is_live:
        if lead.get("has_contact_form", 1) == 0:
            pain_points.append("No contact form — enquiries can only come via phone calls")
        if lead.get("has_blog", 0) == 0:
            pain_points.append("No content/blog — poor SEO ranking and low organic traffic")
        if lead.get("has_testimonials", 0) == 0:
            pain_points.append("No testimonials or reviews displayed — missing social proof for new customers")
        if not lead.get("social_links", ""):
            pain_points.append("No social media links on website — missing community-building touchpoints")

    # Email
    confidence = lead.get("email_confidence", "none")
    if not lead.get("email") and confidence == "none":
        pain_points.append("No email contact found — digital outreach campaigns not possible")

    return pain_points

# Industry defaults mapping
INDUSTRY_SERVICES: dict[str, list[str]] = {
    "Real Estate": [
        "Professional Property Website",
        "CRM & Lead Nurturing Automation",
        "WhatsApp Enquiry Bot",
        "Property Listing Management System",
        "Google Ads & Local SEO Setup",
        "AI Chatbot for Property Queries",
    ],
    "Healthcare": [
        "AI Appointment Booking Bot",
        "WhatsApp Health Reminder System",
        "Patient Management Website",
        "Google My Business Optimization",
        "Online Consultation Booking",
    ],
    "Restaurant & Food": [
        "Online Ordering System",
        "WhatsApp Menu & Order Bot",
        "Restaurant Website with Menu",
        "Google Reviews Management",
        "Food Delivery Integration",
    ],
    "Education": [
        "Student Admission Website",
        "WhatsApp Enquiry Automation",
        "Online Course Registration System",
        "AI FAQ Chatbot",
        "Google Ads for Student Enrollment",
    ],
    "Retail & Shopping": [
        "E-Commerce Website",
        "WhatsApp Catalogue Bot",
        "Inventory Management System",
        "Google Shopping Ads",
        "Loyalty Program App",
    ],
    "Automobile": [
        "Service Booking Website",
        "WhatsApp Service Reminder Bot",
        "Online Appointment System",
        "Customer Follow-Up Automation",
    ],
    "Salon & Beauty": [
        "Online Slot Booking System",
        "WhatsApp Appointment Bot",
        "Beauty Services Website",
        "Customer Loyalty Program",
    ],
    "Finance": [
        "Lead Capture Landing Page",
        "WhatsApp Consultation Bot",
        "EMI Calculator Widget",
        "CRM for Client Management",
    ],
    "IT & Technology": [
        "Modern Portfolio Website",
        "Client Onboarding Automation",
        "WhatsApp Support Bot",
        "Project Showcase System",
    ],
    "Legal": [
        "Professional Law Firm Website",
        "Online Consultation Booking",
        "WhatsApp Case Enquiry Bot",
        "Client Document Portal",
    ],
    "General Business": [
        "Professional Business Website",
        "WhatsApp Contact Widget",
        "AI Chatbot for Queries",
        "Google My Business Setup",
        "Local SEO Optimization",
    ],
}

# Pain point overrides
PAIN_POINT_SERVICE_MAP: dict[str, str] = {
    "Zero online presence": "Professional Business Website",
    "Website is unreachable": "Emergency Website Rebuild",
    "Outdated website": "Modern Website Redesign",
    "Not mobile-friendly": "Mobile-First Website Redesign",
    "Critically slow website": "Website Performance Optimization",
    "Slow website": "Website Speed & Hosting Upgrade",
    "No HTTPS": "SSL Certificate & Security Setup",
    "No AI chatbot": "AI Chatbot Integration",
    "No online appointment": "Online Booking System",
    "No WhatsApp": "WhatsApp Business Integration",
    "No contact form": "Lead Capture Form Setup",
    "No content/blog": "Content Marketing & SEO Blog",
    "No testimonials": "Review Collection & Display System",
    "No social media links": "Social Media Integration",
    "No email contact": "Email Marketing Funnel Setup",
}

def recommend_services(lead: dict, pain_points: list[str]) -> list[str]:
    """
    Combine industry defaults with pain-point-specific recommendations.
    Returns top 5 unique services sorted by priority.
    """
    industry = lead.get("industry_detected", "General Business")
    services: list[str] = []

    for pp in pain_points:
        for keyword, service in PAIN_POINT_SERVICE_MAP.items():
            if keyword.lower() in pp.lower() and service not in services:
                services.append(service)

    industry_defaults = INDUSTRY_SERVICES.get(industry, INDUSTRY_SERVICES["General Business"])
    for svc in industry_defaults:
        if svc not in services:
            services.append(svc)

    return services[:5]

# Pitch templates
OUTREACH_TEMPLATES = {
    "no_website": (
        "Your {industry} business currently has no website, making you completely invisible "
        "to customers searching on Google. We build fast, mobile-ready websites that generate "
        "leads 24/7 — fully set up within 7 days."
    ),
    "dead_website": (
        "Your business website is currently unreachable, meaning every customer who searches "
        "for you online hits a dead end. We can rebuild and host a professional site that goes "
        "live within 5 days."
    ),
    "outdated": (
        "Your current website appears outdated and may be losing trust with modern buyers. "
        "A redesigned, mobile-first site with AI chat and WhatsApp integration can increase "
        "your enquiries by 3× within 90 days."
    ),
    "no_chatbot_booking": (
        "Your {industry} business has no chatbot or online booking — meaning every after-hours "
        "enquiry goes unanswered. An AI appointment bot can capture leads automatically, "
        "even while you sleep."
    ),
    "no_whatsapp": (
        "Your website has no WhatsApp button — yet 85%+ of your potential customers in India "
        "prefer WhatsApp over phone calls. We can add instant WhatsApp contact and an "
        "automated reply bot within 24 hours."
    ),
    "slow_mobile": (
        "Your website scores poorly on mobile speed, causing visitors to leave before seeing "
        "your services. We optimize sites to load under 2 seconds and rank higher on Google."
    ),
    "generic": (
        "Your {industry} business has several digital growth opportunities we have identified. "
        "Our AI-powered lead generation and website solutions can help you capture more "
        "customers online automatically."
    ),
}

def generate_outreach_angle(lead: dict, pain_points: list[str], recommended_services: list[str]) -> str:
    """Generate a personalized cold outreach pitch."""
    industry = lead.get("industry_detected") or lead.get("category") or "business"
    has_web  = bool(lead.get("website") and str(lead.get("website", "")).strip())
    is_live  = lead.get("is_live", 0) == 1

    if not has_web:
        template_key = "no_website"
    elif not is_live:
        template_key = "dead_website"
    elif lead.get("is_outdated", 0) == 1:
        template_key = "outdated"
    elif lead.get("has_chatbot", 1) == 0 and lead.get("has_booking", 1) == 0:
        template_key = "no_chatbot_booking"
    elif lead.get("has_whatsapp", 1) == 0:
        template_key = "no_whatsapp"
    elif lead.get("is_mobile_ready", 1) == 0 or (lead.get("page_speed_score") or 100) < 50:
        template_key = "slow_mobile"
    else:
        template_key = "generic"

    angle = OUTREACH_TEMPLATES[template_key].format(industry=industry)

    if recommended_services:
        top_service = recommended_services[0]
        angle += f" Our recommended first step: **{top_service}**."

    return angle.strip()

def process_pain_intelligence_batch(leads: list[dict]) -> list[dict]:
    """Run pain detection and outreach generator."""
    print("=" * 70)
    print(f"[Layers 5-7] PAIN POINT + RECOMMENDATION + OUTREACH — {len(leads)} leads")
    print("=" * 70)

    results: list[dict] = []
    for lead in leads:
        try:
            pain_points        = detect_pain_points(lead)
            services           = recommend_services(lead, pain_points)
            outreach_angle     = generate_outreach_angle(lead, pain_points, services)

            enriched = {**lead}
            enriched["pain_points"]           = json.dumps(pain_points, ensure_ascii=False)
            enriched["recommended_services"]  = json.dumps(services, ensure_ascii=False)
            enriched["outreach_angle"]        = outreach_angle

            top_pp = pain_points[0][:60] if pain_points else "None"
            print(f"  [PainEngine] {lead.get('business_name','?')[:35]} → {len(pain_points)} pains | Top: {top_pp}")
            results.append(enriched)
        except Exception as e:
            logger.error(f"Pain engine failed for {lead.get('business_name')}: {e}")
            lead.setdefault("pain_points", "[]")
            lead.setdefault("recommended_services", "[]")
            lead.setdefault("outreach_angle", "")
            results.append(lead)

    print(f"[PainEngine] Complete. {len(results)} leads enriched.")
    return results
