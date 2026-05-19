# Project_intelligence_hub/app/api/dependencies.py
from fastapi import Header, HTTPException
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

async def verify_backend(x_backend_service: str = Header(None)):
    logger.warning(f"ENV TOKEN: '{settings.BACKEND_API_TOKEN}'")
    logger.warning(f"RECEIVED:  '{x_backend_service}'")
    if x_backend_service != settings.BACKEND_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized Backend")
    return True