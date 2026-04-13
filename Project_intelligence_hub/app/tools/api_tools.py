# Project_intelligence_hub/app/tools/api_tools.py
import requests, logging, json, redis
from typing import Dict, Optional, List, Any
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    logger.error(f"Failed to initialize Redis client in api_tools: {e}")
    redis_client = None

def fetch_from_cache_or_api(cache_key: str, api_url: str, timeout: int = 15) -> Any:
    if redis_client:
        try:
            cached_data = redis_client.get(cache_key)
            if cached_data:
                logger.info(f"🟢 [REDIS HIT] Loaded {cache_key} instantly.")
                return json.loads(cached_data)
        except redis.RedisError as e:
            logger.warning(f"Redis get error for {cache_key}: {e}")
    
    # Cache Miss - Fetch from API
    logger.info(f"🌐 [REDIS MISS] Fetching fresh data from {api_url}...")
    try:
        response = requests.get(api_url, timeout=timeout)
        response.raise_for_status()
        
        data = response.json().get("data")
        
        if not data:
            return None
        
        # Save to Redis (5-minute TTL)
        if redis_client:
            try:
                redis_client.setex(cache_key, 300, json.dumps(data))
                logger.info(f"💾 Saved {cache_key} to Redis.")
            except redis.RedisError as e:
                logger.warning(f"Redis set error for {cache_key}: {e}")
        
        return data
    
    except Exception as e:
        logger.error(f"API Fetch Error for {api_url}: {e}")
        return None


def fetch_live_project_data(project_id: str) -> Optional[Dict]:
    primary_url = f"{settings.SINGLE_PROJECT_API}/{project_id}"
    primary_cache_key = f"cache:project:{project_id}"
    
    logger.info(f"Attempting Primary API for Project {project_id}...")
    primary_data = fetch_from_cache_or_api(cache_key=primary_cache_key, api_url=primary_url, timeout=10)
    
    if primary_data:
        # Handle backend array-wrapping variations gracefully
        if isinstance(primary_data, list) and len(primary_data) > 0:
            logger.info(f"Extracted Project {project_id} from Primary API.")
            return primary_data[0]
        elif isinstance(primary_data, dict):
            logger.info(f"Extracted Project {project_id} from Primary API.")
            return primary_data
    
    logger.warning(f"Primary API failed or returned empty for {project_id}. Initiating FALLBACK to Backup API...")
    
    backup_url = settings.PROJECTS_WITH_RAIDD_API
    backup_cache_key = "cache:all_projects_backup"
    
    backup_data = fetch_from_cache_or_api(cache_key=backup_cache_key, api_url=backup_url, timeout=20)
    
    if backup_data and isinstance(backup_data, list):
        for item in backup_data:
            proj = item.get("project", {})
            if proj.get("id") == project_id:
                logger.info(f"Found Project {project_id} using Backup API.")
                return item
    
    logger.error(f"CRITICAL: Project ID {project_id} could not be retrieved from Primary OR Backup APIs.")
    return None

def fetch_all_emails() -> List[Dict]:
    return fetch_from_cache_or_api(
        cache_key="cache:all_emails", 
        api_url=settings.ALL_EMAILS_API, 
        timeout=15
    )

def fetch_ai_detections() -> List[Dict]:
    return fetch_from_cache_or_api(
        cache_key="cache:all_detections", 
        api_url=settings.AI_DETECTION_API, 
        timeout=15
    )