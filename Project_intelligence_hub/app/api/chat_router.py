# Project_intelligence_hub/app/api/chat_router.py
import logging
from fastapi import APIRouter, HTTPException
from app.schemas.chat_schemas import ChatRequest, ChatResponse
from app.services.chatbot_engine import generate_chat_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Conversational AI"])

@router.post("/", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        logger.info(f"Received chat message for session {request.session_id}")
        result = generate_chat_response(
            message=request.message,
            session_id=request.session_id, 
            project_id=request.project_id
        )
        return ChatResponse(reply=result["reply"], sources=result["sources"])
    except Exception as e:
        logger.error(f"Chatbot Error: {e}", exc_info=True) 
        raise HTTPException(status_code=500, detail="The AI encountered an error processing your request.")
