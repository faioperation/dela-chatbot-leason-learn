from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings


async def verify_backend(
    backend_service_value: Optional[str] = Header(
        default=None,
        alias=settings.BACKEND_SERVICE_HEADER_NAME,
        description="Value",
        example="Value",
    )
):
    if not backend_service_value:
        raise HTTPException(
            status_code=401,
            detail=f"Missing {settings.BACKEND_SERVICE_HEADER_NAME} header.",
        )

    if backend_service_value != settings.BACKEND_SERVICE_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized Backend",
        )

    return True