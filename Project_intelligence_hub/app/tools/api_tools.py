# Project_intelligence_hub/app/tools/api_tools.py
import requests, logging, json, redis
from typing import Dict, Optional, List, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis setup
try:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None

def fetch_from_cache_or_api(cache_key: str, api_url: str, timeout: int = 15) -> Any:
    """Helper to fetch data with Redis support."""
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"[REDIS HIT] {cache_key}")
                return json.loads(cached_data)
        except: pass
    
    try:
        headers = {"x-backend-service": settings.BACKEND_API_TOKEN}
        response = requests.get(api_url, timeout=timeout, headers=headers)
        response.raise_for_status()
        data = response.json().get("data")
        
        if redis_client and data:
            try:
                redis_client.setex(cache_key, 300, json.dumps(data))
            except: pass
        return data
    except Exception as e:
        logger.error(f"API Fetch Error for {api_url}: {e}")
        return None

def fetch_live_project_data(project_id: str) -> Optional[Dict]:
    """Fetches project, RAIDD, and vendor portfolio data with robust ID matching."""
    headers = {"x-backend-service": settings.BACKEND_API_TOKEN}
    
    try:
        # 1. Fetch Master List
        logger.info(f"Fetching master list from: {settings.PROJECTS_WITH_RAIDD_API}")
        all_res = requests.get(settings.PROJECTS_WITH_RAIDD_API, headers=headers, timeout=15)
        all_res.raise_for_status()
        
        all_data = all_res.json().get("data") or []
        logger.info(f"Master list fetched. Total items: {len(all_data)}")

        # 2. Search for target project in Master List (Improved logic)
        target_item = None
        for p in all_data:
            # Check multiple possible locations for project ID
            potential_id = p.get("id") or p.get("project", {}).get("id") or p.get("project_id")
            
            if potential_id == project_id:
                target_item = p
                logger.info(f"✅ Match found in Master List for ID: {project_id}")
                break
        
        # 3. Fallback to Single Project API if not found in Master List
        if not target_item:
            logger.info(f"❌ Project ID {project_id} not in Master List. Trying Single API...")
            single_url = f"{settings.SINGLE_PROJECT_API}/{project_id}"
            s_res = requests.get(single_url, headers=headers, timeout=15)
            
            if s_res.status_code == 200:
                s_data = s_res.json().get("data")
                if isinstance(s_data, list) and len(s_data) > 0:
                    target_item = s_data[0]
                elif isinstance(s_data, dict):
                    target_item = s_data
                logger.info(f"✅ Match found in Single Project API for ID: {project_id}")
            else:
                logger.error(f"❌ Single API returned status: {s_res.status_code}")

        if not target_item:
            logger.error(f"❌ CRITICAL: Project ID {project_id} not found anywhere.")
            return None

        # 4. Dynamic Vendor Analysis (The logic to add vendor context)
        # We normalize the data structure here so the rest of the engine doesn't crash
        proj_info = target_item.get("project") if isinstance(target_item.get("project"), dict) else target_item
        
        # Ensure proj_info is a dictionary
        if not isinstance(proj_info, dict):
             # If the structure is different, try to find the project dict inside target_item
             proj_info = target_item 

        v_id = proj_info.get("vendorId") or proj_info.get("vendor", {}).get("id")
        v_name = proj_info.get("vendorName") or proj_info.get("vendor", {}).get("name") or "Unknown"
        
        if v_id and all_data:
            # Filter portfolio from the already fetched master list to save API calls
            portfolio = []
            for p in all_data:
                p_v_id = p.get("vendorId") or p.get("project", {}).get("vendorId") or p.get("vendor", {}).get("id")
                if p_v_id == v_id:
                    portfolio.append(p)
            
            bad_health_count = 0
            for p in portfolio:
                p_health = p.get("projectHealth") or p.get("project", {}).get("projectHealth")
                if p_health == "Bad":
                    bad_health_count += 1
            
            target_item["vendor_analysis"] = {
                "name": v_name,
                "total_owned": len(portfolio),
                "bad_health_count": bad_health_count,
                "risk_summary": f"Vendor '{v_name}' manages {len(portfolio)} projects. {bad_health_count} of them are in Bad Health."
            }
            logger.info(f"Vendor Analysis complete for: {v_name}")

        return target_item

    except Exception as e:
        logger.error(f"Fetcher Error in fetch_live_project_data: {e}", exc_info=True)
        return None


def fetch_all_emails() -> List[Dict]:
    return fetch_from_cache_or_api("cache:all_emails", settings.ALL_EMAILS_API) or []

def fetch_ai_detections() -> List[Dict]:
    return fetch_from_cache_or_api("cache:all_detections", settings.AI_DETECTION_API) or []

def fetch_user_emails(user_id: str) -> List[Dict]:
    url = f"{settings.USER_EMAILS_API}{user_id}"
    return fetch_from_cache_or_api(f"cache:user_emails:{user_id}", url) or []