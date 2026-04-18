# Project_intelligence_hub/app/api/dependencies.py
from fastapi import Header, HTTPException
import logging

logger = logging.getLogger(__name__)

async def verify_backend(x_backend_service: str = Header(None)):
    if x_backend_service != "PROJECT_AI_BACKEND":
        logger.warning(f"Unauthorized access attempt blocked. Provided token: {x_backend_service}")
        raise HTTPException(status_code=401, detail="Unauthorized Backend")
    
    return True