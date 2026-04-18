# Project_intelligence_hub/app/api/email_router.py
import logging
from fastapi import APIRouter, HTTPException, Depends
from app.services.email_writer_engine import draft_email_reply
from app.api.dependencies import verify_backend
from app.schemas.email_schemas import DraftReplyRequest, DraftReplyResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/emails", tags=["Auto-Responder"], dependencies=[Depends(verify_backend)])

@router.post("/draft-reply", response_model=DraftReplyResponse)
def api_draft_reply(request: DraftReplyRequest):
    try:
        logger.info(f"Drafting reply for email ID: {request.email_id} (User: {request.user_id})")
        
        response_data = draft_email_reply(
            user_id=request.user_id, 
            email_id=request.email_id, 
            instructions=request.instructions
        )
        
        return response_data
    
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Internal Server Error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while drafting the email.")