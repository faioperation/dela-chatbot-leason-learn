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
        response_data = generate_lessons_learned(request.project_id)
        return response_data
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Internal Server Error: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating insights.")