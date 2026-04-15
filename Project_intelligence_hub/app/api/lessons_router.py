# Project_intelligence_hub/app/api/lessons_router.py
import logging
from fastapi import APIRouter, HTTPException
from app.services.lessons_engine import generate_lessons_learned
from app.schemas.lessons_schemas import LessonsRequest, LessonsLearnedResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/insights", tags=["Predictive Insights"])

@router.post("/lessons-learned", response_model=LessonsLearnedResponse)
def get_lessons_learned(request: LessonsRequest):
    try:
        logger.info(f"Received request for Lessons Learned on Project: {request.project_id}")
        return generate_lessons_learned(request.project_id)
    
    except ValueError as ve:
        logger.warning(f"Rejecting request due to external data issue: {ve}")
        raise HTTPException(
            status_code=502, 
            detail=f"External Backend Dependency Error: {str(ve)}"
        )
        
    except Exception as e:
        logger.error(f"Internal Server Error in AI Logic: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="An internal AI processing error occurred."
        )
