# Project_intelligence_hub/app/tools/api_tools.py
import requests, logging
from typing import Dict, Optional, List
from cachetools import cached, TTLCache
from app.core.config import settings

logger = logging.getLogger(__name__)

project_cache   = TTLCache(maxsize=1, ttl=300)
email_cache     = TTLCache(maxsize=1, ttl=300)
detection_cache = TTLCache(maxsize=1, ttl=300)

@cached(cache=project_cache)
def _fetch_all_projects_cached() -> List[Dict]:
    url = settings.PROJECTS_WITH_RAIDD_API
    logger.info(f"[CACHE MISS] Fetching massive live data from {url}...")
    
    response = requests.get(url, timeout=20) 
    response.raise_for_status()
    return response.json().get("data",[])

def fetch_live_project_data(project_id: str) -> Optional[Dict]:
    try:
        data = _fetch_all_projects_cached()
        
        for item in data:
            proj = item.get("project", {})
            if proj.get("id") == project_id:
                logger.info(f"Found Project ID {project_id} in cache.")
                return item
                
        logger.warning(f"Project ID {project_id} not found in the backend response.")
        return None
    
    except Exception as e:
        logger.error(f"Failed to fetch live project data: {e}", exc_info=True)
        return None

@cached(cache=email_cache)
def fetch_all_emails() -> List[Dict]:
    url = settings.ALL_EMAILS_API
    logger.info(f"[CACHE MISS] Fetching massive email data from {url}...")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json().get("data",[])
    except Exception as e:
        logger.error(f"Failed to fetch emails: {e}")
        return[]

@cached(cache=detection_cache)
def fetch_ai_detections() -> List[Dict]:
    url = settings.AI_DETECTION_API
    logger.info(f"[CACHE MISS] Fetching massive AI detection data from {url}...")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.json().get("data",[])
    except Exception as e:
        logger.error(f"Failed to fetch AI detections: {e}")
        return[]