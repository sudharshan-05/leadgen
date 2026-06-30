"""
analytics/website_analyser.py — Deep Website Analyser.
Performs comprehensive audits on scraped lead websites in parallel.
"""
from __future__ import annotations

import re
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import config
from database import save_leads_bulk

logger = logging.getLogger(__name__)

# Reusable patterns
PHONE_REGEX = re.compile(r"[\+]?[\d][\d\s\-\(\)\.]{8,20}[\d]")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
YEAR_REGEX = re.compile(r"\b(20\d{2})\b")

def default_analysis_results() -> dict:
    """Return default schema for website analysis."""
    return {
        "is_live": 0,
        "has_https": 0,
        "ssl_valid": 0,
        "is_mobile_ready": 0,
        "has_chatbot": 0,
        "has_whatsapp": 0,
        "has_booking": 0,
        "has_contact_form": 0,
        "has_sitemap": 0,
        "has_pricing_page": 0,
        "broken_links_count": 0,
        "is_outdated": 0,
        "copyright_year": 0,
        "load_time": 0.0,
        "page_speed_score": 0,
        "website_score": 0,
        "website_status_label": "no_website",
        "website_status_confidence": 1.0,
        "cms_detected": "Custom",
        "detected_technologies": "[]",
        "redirect_count": 0,
        "final_url": "",
        "social_links": "",
        "page_title": "",
        "meta_description": "",
        "services_mentioned": "",
        "has_phone_on_page": 0,
        "has_email_on_page": 0,
        "has_address_on_page": 0,
        "has_testimonials": 0,
        "has_team_page": 0,
        "has_blog": 0,
        "estimated_page_count": 0
    }

def audit_single_website(url: str) -> dict:
    """Perform a deep analysis on a single business website."""
    results = default_analysis_results()
    if not url or not url.strip():
        return results
        
    target_url = url.strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url
        
    results["final_url"] = target_url
    results["has_https"] = 1 if target_url.startswith("https://") else 0
    
    headers = {"User-Agent": config.USER_AGENTS[0]}
    
    start_time = time.time()
    try:
        resp = requests.get(target_url, headers=headers, timeout=config.WEBSITE_TIMEOUT, allow_redirects=True)
        load_time = time.time() - start_time
        
        results["is_live"] = 1 if resp.status_code < 400 else 0
        results["load_time"] = round(load_time, 3)
        results["redirect_count"] = len(resp.history)
        results["final_url"] = resp.url
        results["has_https"] = 1 if resp.url.startswith("https://") else 0
        
        # Approximate speed score
        if load_time < 2.0:
            results["page_speed_score"] = 100
        elif load_time < 4.0:
            results["page_speed_score"] = 70
        elif load_time < 6.0:
            results["page_speed_score"] = 40
        else:
            results["page_speed_score"] = 10
            
        if resp.status_code >= 400:
            results["page_speed_score"] = 0
            return results
            
        # Parse HTML
        soup = BeautifulSoup(resp.text, "html.parser")
        html_lower = resp.text.lower()
        body_text = soup.get_text()
        body_text_lower = body_text.lower()
        
        # 1. MOBILE READINESS (Score 0-100)
        mobile_score = 0
        has_viewport = bool(soup.find("meta", attrs={"name": "viewport"}))
        if has_viewport:
            mobile_score += 40
            
        style_tags = soup.find_all("style")
        has_media_query = any("@media" in style.get_text() for style in style_tags)
        if has_media_query:
            mobile_score += 30
            
        frameworks = ["bootstrap", "tailwind", "foundation", "bulma"]
        has_css_framework = any(fw in html_lower for fw in frameworks)
        if has_css_framework:
            mobile_score += 15
            
        hamburger_selectors = ["navbar-toggler", "hamburger", "nav-toggle", "menu-toggle"]
        has_hamburger = any(any(h_sel in str(el) for h_sel in hamburger_selectors) for el in soup.find_all(class_=True))
        if has_hamburger:
            mobile_score += 15
            
        results["is_mobile_ready"] = 1 if mobile_score >= 70 else 0
        
        # 2. TECHNOLOGY DETECTION
        technologies: list[str] = []
        if "/wp-content/" in html_lower or "/wp-includes/" in html_lower:
            results["cms_detected"] = "WordPress"
            technologies.append("WordPress")
        elif "wix.com" in html_lower:
            results["cms_detected"] = "Wix"
            technologies.append("Wix")
        elif "squarespace.com" in html_lower or "static1.squarespace.com" in html_lower:
            results["cms_detected"] = "Squarespace"
            technologies.append("Squarespace")
        elif "cdn.shopify.com" in html_lower or "shopify.shop" in html_lower:
            results["cms_detected"] = "Shopify"
            technologies.append("Shopify")
        elif "webflow.com" in html_lower or "data-wf-page" in html_lower:
            results["cms_detected"] = "Webflow"
            technologies.append("Webflow")
        elif "blogger.com" in html_lower:
            results["cms_detected"] = "Blogger"
            technologies.append("Blogger")
        else:
            results["cms_detected"] = "Custom"

        if "react" in html_lower or "_next/static" in html_lower or "__next" in html_lower:
            if "_next/static" in html_lower or "__next" in html_lower:
                technologies.append("Next.js")
            else:
                technologies.append("React")
        if "vue" in html_lower and ("v-bind" in html_lower or "v-if" in html_lower or "vuex" in html_lower):
            technologies.append("Vue.js")
        if "angular" in html_lower and "ng-version" in html_lower:
            technologies.append("Angular")
        if "hubspot" in html_lower or "hs-scripts" in html_lower:
            technologies.append("HubSpot")
        if "intercom" in html_lower:
            technologies.append("Intercom")
        if "calendly.com" in html_lower:
            technologies.append("Calendly")
        if "googletagmanager" in html_lower:
            technologies.append("Google Tag Manager")
        if "google-analytics" in html_lower or "gtag" in html_lower:
            technologies.append("Google Analytics")
        if "bootstrap" in html_lower:
            technologies.append("Bootstrap")
        if "jquery" in html_lower:
            technologies.append("jQuery")

        import json as _json
        results["detected_technologies"] = _json.dumps(list(set(technologies)), ensure_ascii=False)
            
        # Chatbot
        chatbot_signatures = ["tidio", "intercom", "drift", "freshchat", "crisp", "tawk.to", "zendesk", "livechat", "olark", "smartsupp", "botpress", "landbot", "manychat"]
        results["has_chatbot"] = 1 if any(sig in html_lower for sig in chatbot_signatures) else 0

        # WhatsApp Widget
        results["has_whatsapp"] = 1 if ("wa.me" in html_lower or "api.whatsapp.com" in html_lower or "whatsapp.com/send" in html_lower) else 0

        # Booking
        has_calendar = any(sig in html_lower for sig in ["calendly.com", "booksy.com", "acuityscheduling", "simplybook", "setmore"])
        booking_keywords = ["book now", "book appointment", "schedule a call", "book online", "make appointment", "reserve now", "book a slot"]
        has_booking_text = any(kw in body_text_lower for kw in booking_keywords)
        results["has_booking"] = 1 if (has_calendar or has_booking_text) else 0

        # Contact Form
        has_form = bool(soup.find("form"))
        if has_form:
            forms = soup.find_all("form")
            contact_form_found = False
            for form in forms:
                inputs = form.find_all(["input", "textarea"])
                input_types = [inp.get("type", "").lower() for inp in inputs]
                input_names = [inp.get("name", "").lower() for inp in inputs]
                all_text = " ".join(input_types + input_names)
                if any(kw in all_text for kw in ["email", "phone", "tel", "name", "message", "contact"]):
                    contact_form_found = True
                    break
            results["has_contact_form"] = 1 if contact_form_found else 0

        # Sitemap
        try:
            sitemap_url = resp.url.rstrip("/") + "/sitemap.xml"
            sm_resp = requests.get(sitemap_url, headers=headers, timeout=5)
            results["has_sitemap"] = 1 if sm_resp.status_code == 200 and "xml" in sm_resp.text[:100].lower() else 0
        except Exception:
            results["has_sitemap"] = 0

        # Pricing page
        pricing_keywords = ["pricing", "our plans", "packages", "price list", "fees", "tariff", "rate card"]
        results["has_pricing_page"] = 1 if any(kw in body_text_lower for kw in pricing_keywords) else 0

        # SSL valid
        import ssl as _ssl, socket as _socket
        try:
            parsed_host = urlparse(resp.url).hostname or ""
            if parsed_host and resp.url.startswith("https"):
                ctx = _ssl.create_default_context()
                with ctx.wrap_socket(_socket.create_connection((parsed_host, 443), timeout=5), server_hostname=parsed_host) as ssock:
                    results["ssl_valid"] = 1 if ssock.getpeercert() else 0
            else:
                results["ssl_valid"] = 0
        except Exception:
            results["ssl_valid"] = 0
        
        # Social Media Links
        socials = []
        for tag in soup.find_all("a", href=True):
            href = tag["href"].lower()
            if any(plat in href for plat in ["facebook.com", "instagram.com", "linkedin.com", "twitter.com", "youtube.com", "x.com"]):
                socials.append(tag["href"])
        results["social_links"] = ", ".join(list(set(socials))[:5])
        
        # 3. DESIGN AGE DETECTION
        old_signals = 0
        is_outdated_verdict = False
        
        years = YEAR_REGEX.findall(body_text)
        if years:
            max_year = max(int(y) for y in years)
            results["copyright_year"] = max_year
            if max_year < 2020:
                is_outdated_verdict = True
                
        tables = soup.find_all("table")
        table_layout = False
        for table in tables:
            tds = table.find_all("td")
            if tds and any(td.get("width") or "width" in (td.get("style") or "") for td in tds):
                table_layout = True
                break
        if table_layout:
            is_outdated_verdict = True
            
        if soup.find("font"):
            is_outdated_verdict = True
            
        total_elements = len(soup.find_all())
        styled_elements = len(soup.find_all(style=True))
        if total_elements > 0 and (styled_elements / total_elements) > 0.3:
            old_signals += 1
            
        if not has_css_framework:
            old_signals += 1
            
        images = soup.find_all("img", src=True)
        if images:
            all_old_formats = True
            for img in images:
                src = img["src"].lower()
                if ".webp" in src or ".svg" in src:
                    all_old_formats = False
                    break
            if all_old_formats:
                old_signals += 1
                
        if is_outdated_verdict or old_signals >= 2:
            results["is_outdated"] = 1
            
        # 4. CONTENT INTELLIGENCE
        title_tag = soup.find("title")
        results["page_title"] = title_tag.get_text().strip()[:200] if title_tag else ""
        
        meta_desc = soup.find("meta", attrs={"name": "description"})
        results["meta_description"] = meta_desc.get("content", "").strip()[:500] if meta_desc else ""
        
        headers_text = []
        for tag in soup.find_all(["h1", "h2", "h3"]):
            txt = tag.get_text().strip()
            if txt and len(txt) > 5 and len(txt) < 80:
                headers_text.append(txt)
        results["services_mentioned"] = ", ".join(list(set(headers_text))[:5])
        
        results["has_phone_on_page"] = 1 if PHONE_REGEX.search(body_text) else 0
        results["has_email_on_page"] = 1 if EMAIL_REGEX.search(body_text) else 0
        
        address_keywords = ["street", "road", "ave", "lane", "building", "nagar", "chennai", "bangalore", "mumbai", "delhi", "floor", "block"]
        results["has_address_on_page"] = 1 if any(kw in body_text_lower for kw in address_keywords) else 0
        
        testimonial_keywords = ["testimonial", "testimonials", "review", "reviews", "client said", "what our clients say"]
        results["has_testimonials"] = 1 if any(kw in body_text_lower for kw in testimonial_keywords) else 0
        
        team_keywords = ["our team", "meet the team", "about us", "about our"]
        results["has_team_page"] = 1 if any(kw in body_text_lower for kw in team_keywords) else 0
        
        blog_found = 0
        for tag in soup.find_all("a", href=True):
            href = tag["href"].lower()
            if "/blog" in href or "blog" in tag.get_text().lower():
                blog_found = 1
                break
        results["has_blog"] = blog_found
        
        parsed_base = urlparse(resp.url)
        internal_links = set()
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            abs_href = urljoin(resp.url, href)
            if urlparse(abs_href).netloc == parsed_base.netloc:
                internal_links.add(abs_href)
        results["estimated_page_count"] = len(internal_links)
        
        # 5. WEBSITE STATUS CLASSIFICATION
        outdated_signals = 0
        modern_signals = 0

        if results["is_mobile_ready"] == 1:        modern_signals += 1
        if results["has_https"] == 1:              modern_signals += 1
        if results["ssl_valid"] == 1:              modern_signals += 1
        if results["has_chatbot"] == 1:            modern_signals += 2
        if results["has_booking"] == 1:            modern_signals += 1
        if results["has_whatsapp"] == 1:           modern_signals += 1
        if results["page_speed_score"] >= 70:      modern_signals += 1
        if results["has_contact_form"] == 1:       modern_signals += 1
        if results["has_blog"] == 1:               modern_signals += 1

        if results["is_outdated"] == 1:            outdated_signals += 3
        if results["is_mobile_ready"] == 0:        outdated_signals += 2
        if results["has_https"] == 0:              outdated_signals += 2
        if results["page_speed_score"] < 40:       outdated_signals += 2
        if results["has_chatbot"] == 0:            outdated_signals += 1
        if results["has_booking"] == 0:            outdated_signals += 1
        if results["has_contact_form"] == 0:       outdated_signals += 1

        total_signals = outdated_signals + modern_signals
        if total_signals == 0:
            label = "average"
            confidence = 0.5
        elif modern_signals >= 6:
            label = "modern"
            confidence = round(min(0.99, modern_signals / max(total_signals, 1)), 2)
        elif outdated_signals >= 5:
            label = "outdated"
            confidence = round(min(0.99, outdated_signals / max(total_signals, 1)), 2)
        else:
            label = "average"
            confidence = round(0.5 + abs(modern_signals - outdated_signals) / (total_signals * 2), 2)

        results["website_status_label"] = label
        results["website_status_confidence"] = confidence

        # 6. OVERALL WEBSITE SCORE
        w_score = 0
        if results["is_live"] == 1:
            w_score += 15
        if results["has_https"] == 1:
            w_score += 10
        if results["is_mobile_ready"] == 1:
            w_score += 15
        if load_time < 3.0:
            w_score += 10
        if results["is_outdated"] == 0:
            w_score += 10
        if results["has_chatbot"] == 1:
            w_score += 10
        if results["has_booking"] == 1:
            w_score += 10
        if results["has_email_on_page"] == 1:
            w_score += 10
        if results["has_phone_on_page"] == 1:
            w_score += 10
            
        results["website_score"] = w_score
        
    except Exception as e:
        logger.error(f"Audit failed for website {url}: {e}")
        
    return results

def audit_leads_websites(leads: list[dict]) -> list[dict]:
    """Perform website auditing in parallel using ThreadPoolExecutor and update PostgreSQL."""
    print("=" * 70)
    print(f"Starting Website Analysis on {len(leads)} leads...")
    print("=" * 70)
    
    audited_leads = []
    
    with ThreadPoolExecutor(max_workers=config.WEBSITE_ANALYSER_WORKERS) as executor:
        futures = {}
        for idx, lead in enumerate(leads, start=1):
            website = lead.get("website") or ""
            if website:
                futures[executor.submit(audit_single_website, website)] = (idx, lead)
            else:
                blank_results = default_analysis_results()
                blank_results["website_score"] = 0
                updated_lead = {**lead, **blank_results}
                audited_leads.append(updated_lead)
                
        completed = len(audited_leads)
        total = len(leads)
        
        for fut in futures:
            idx, lead = futures[fut]
            completed += 1
            print(f"Analysing website {completed}/{total}...")
            
            try:
                analysis = fut.result()
                updated_lead = {**lead, **analysis}
                audited_leads.append(updated_lead)
            except Exception as e:
                logger.error(f"Failed resolving audit future for lead {lead.get('business_name')}: {e}")
                blank_results = default_analysis_results()
                updated_lead = {**lead, **blank_results}
                audited_leads.append(updated_lead)
                
    print("\nUpdating database with website analysis results...")
    save_leads_bulk(audited_leads)
    print("Database update complete.")
    
    return audited_leads
