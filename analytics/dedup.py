"""
analytics/dedup.py - Deduplication Engine.
Removes duplicates before any processing happens based on 4 rules.
"""
from __future__ import annotations

import logging
from rapidfuzz import fuzz
from database import deduplicate_check, Lead, get_db
from database.crud import _normalize_phone_helper, _extract_domain_helper

logger = logging.getLogger(__name__)

def deduplicate_leads(leads: list[dict], skip_db_check: bool = False) -> list[dict]:
    """
    Deduplicate a list of leads using 4 rules.
    """
    unique_leads: list[dict] = []
    
    seen_place_ids: set[str] = set()
    seen_phones: set[str] = set()
    seen_domains: set[str] = set()
    
    before_count = len(leads)
    duplicate_count = 0
    
    for lead in leads:
        # Check rule 1: place_id
        place_id = lead.get("place_id")
        if place_id:
            if place_id in seen_place_ids:
                duplicate_count += 1
                continue
            if not skip_db_check:
                try:
                    with get_db() as session:
                        exists_db = session.query(Lead.id).filter(Lead.place_id == place_id).first()
                    if exists_db:
                        duplicate_count += 1
                        continue
                except Exception as e:
                    logger.error(f"Error checking place_id in database: {e}")
                
        # Check rule 2: Normalized phone match
        phone = lead.get("phone")
        norm_phone = _normalize_phone_helper(phone)
        if norm_phone:
            if norm_phone in seen_phones:
                duplicate_count += 1
                continue
                
        # Check rule 3: Domain match
        website = lead.get("website")
        domain = _extract_domain_helper(website)
        if domain:
            if domain in seen_domains:
                duplicate_count += 1
                continue
                
        # Check rule 4: Fuzzy name match
        name = lead.get("business_name")
        city = lead.get("city")
        if not skip_db_check and deduplicate_check(phone=phone, domain=domain, name=name, city=city):
            duplicate_count += 1
            continue
            
        is_fuzzy_dup = False
        if name:
            target_name = name.strip().lower()
            for existing in unique_leads:
                existing_name = (existing.get("business_name") or "").strip().lower()
                sim = fuzz.token_sort_ratio(target_name, existing_name)
                if sim > 85:
                    existing_city = (existing.get("city") or "").strip().lower()
                    target_city = (city or "").strip().lower()
                    
                    if target_city and existing_city == target_city:
                        is_fuzzy_dup = True
                        break
                    elif not target_city or not existing_city:
                        target_addr = (lead.get("address") or "").lower()
                        existing_addr = (existing.get("address") or "").lower()
                        if (target_city and target_city in existing_addr) or (existing_city and existing_city in target_addr):
                            is_fuzzy_dup = True
                            break
                        elif not target_city and not existing_city:
                            is_fuzzy_dup = True
                            break
            if is_fuzzy_dup:
                duplicate_count += 1
                continue
                
        if place_id:
            seen_place_ids.add(place_id)
        if norm_phone:
            seen_phones.add(norm_phone)
        if domain:
            seen_domains.add(domain)
            
        unique_leads.append(lead)
        
    after_count = len(unique_leads)
    
    print("Deduplication complete.")
    print(f"Before: {before_count} leads")
    print(f"After: {after_count} leads")
    print(f"Removed: {before_count - after_count} duplicates")
    
    return unique_leads
