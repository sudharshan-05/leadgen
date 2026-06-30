"""
analytics/email_finder.py — Email Intelligence Engine.
Finds and verifies email addresses for leads.
"""
from __future__ import annotations

import re
import time
import random
import logging
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
import dns.resolver
import config
from database import save_leads_bulk

logger = logging.getLogger(__name__)

# Email regex
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

JUNK_KEYWORDS = [
    "example", "test", "noreply", "no-reply", "privacy", 
    "support@wordpress", "admin@wix", "postmaster"
]

def is_valid_email(email: str) -> bool:
    """Return True if email is valid and does not contain junk keywords."""
    email_lower = email.strip().lower()
    if not EMAIL_REGEX.match(email_lower):
        return False
    if any(keyword in email_lower for keyword in JUNK_KEYWORDS):
        return False
    return True

def verify_mx_record(domain: str) -> bool:
    """Check if the domain has active MX records using dnspython."""
    try:
        records = dns.resolver.resolve(domain, 'MX')
        return len(records) > 0
    except Exception:
        return False

def scrape_page_for_emails(url: str, headers: dict) -> list[str]:
    """Fetch a page and extract all valid emails."""
    try:
        resp = requests.get(url, headers=headers, timeout=config.WEBSITE_TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            body_text = soup.get_text()
            emails = EMAIL_REGEX.findall(body_text)
            
            for tag in soup.find_all("a", href=True):
                href = tag["href"].lower()
                if href.startswith("mailto:"):
                    clean_email = href.replace("mailto:", "").split("?")[0].strip()
                    emails.append(clean_email)
                    
            return [email.strip() for email in emails if is_valid_email(email)]
    except Exception as e:
        logger.debug(f"Failed scraping emails from {url}: {e}")
    return []

def find_emails_for_lead(lead: dict) -> dict:
    """
    Search and verify email addresses for a lead.
    Returns:
      {
         "email": str,
         "email_confidence": "found" | "guessed" | "none",
         "all_emails_found": list[str]
      }
    """
    website = lead.get("website") or ""
    business_name = lead.get("business_name") or ""
    city = lead.get("city") or ""
    
    all_emails = []
    
    headers = {"User-Agent": random.choice(config.USER_AGENTS)}
    
    domain = ""
    if website:
        try:
            parsed = urlparse(website.strip().lower())
            domain = parsed.netloc or parsed.path
            if domain.startswith("www."):
                domain = domain[4:]
        except Exception:
            pass
            
    # STEP 1 — DIRECT PAGE SCRAPING
    if website:
        base_url = website.strip()
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url
            
        sub_paths = [
            "", "contact", "contact-us", "about", 
            "about-us", "team", "reach-us", "get-in-touch"
        ]
        
        # Scrape pages
        for path in sub_paths:
            page_url = urljoin(base_url, path) if path else base_url
            page_emails = scrape_page_for_emails(page_url, headers)
            all_emails.extend(page_emails)
            time.sleep(random.uniform(0.5, 1.5))
            
    # STEP 2 — GOOGLE EMAIL SEARCH
    if not all_emails and business_name:
        time.sleep(3.0)
        query = f'"{business_name}" "{city}" email contact'
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                body_text = soup.get_text()
                google_emails = EMAIL_REGEX.findall(body_text)
                all_emails.extend([email.strip() for email in google_emails if is_valid_email(email)])
        except Exception as e:
            logger.error(f"Google email search failed: {e}")
            
    all_emails = list(set(all_emails))
    
    # Verify MX records
    valid_scraped_emails = []
    for email in all_emails:
        email_domain = email.split("@")[-1].strip().lower()
        if verify_mx_record(email_domain):
            valid_scraped_emails.append(email)
            
    if valid_scraped_emails:
        best_email = valid_scraped_emails[0]
        for pref in ["info@", "hello@", "contact@", "enquiry@"]:
            matched = [e for e in valid_scraped_emails if e.lower().startswith(pref)]
            if matched:
                best_email = matched[0]
                break
                
        return {
            "email": best_email,
            "email_confidence": "found",
            "all_emails_found": valid_scraped_emails
        }
        
    # STEP 3 — COMMON EMAIL CONSTRUCTION
    if domain and verify_mx_record(domain):
        first_word = re.sub(r"\W+", "", business_name.split()[0].lower()) if business_name else ""
        guesses = [
            f"info@{domain}",
            f"hello@{domain}",
            f"contact@{domain}",
            f"enquiry@{domain}"
        ]
        if first_word:
            guesses.append(f"{first_word}@{domain}")
            
        return {
            "email": guesses[0],
            "email_confidence": "guessed",
            "all_emails_found": guesses
        }
        
    return {
        "email": "",
        "email_confidence": "none",
        "all_emails_found": []
    }

def process_leads_emails(leads: list[dict]) -> list[dict]:
    """Find and verify emails for a batch of leads."""
    print("=" * 70)
    print(f"Starting Email Intelligence Discovery on {len(leads)} leads...")
    print("=" * 70)
    
    updated_leads = []
    for i, lead in enumerate(leads, start=1):
        print(f"Finding email for lead {i}/{len(leads)}: {lead.get('business_name')}...")
        email_info = find_emails_for_lead(lead)
        updated_lead = {**lead, **email_info}
        updated_leads.append(updated_lead)
        
    save_leads_bulk(updated_leads)
    
    return updated_leads
