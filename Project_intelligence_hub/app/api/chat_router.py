# Project_intelligence_hub/app/api/chat_router.py
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.chat_schemas import ChatRequest, ChatResponse
from app.services.chatbot_engine import generate_chat_response
from app.api.dependencies import verify_backend
from app.services.session_docs_engine import process_session_document
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Conversational AI"], dependencies=[Depends(verify_backend)])

@router.post("/", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        logger.info(f"Received chat message for session {request.session_id}")
        
        if request.document_url:
            logger.info("Document URL detected! Processing file before chatting...")
            try:
                process_session_document(request.document_url, request.session_id)
            except ValueError as ve:
                return ChatResponse(
                    reply=f"I'm sorry, but I couldn't process your document. {str(ve)}", 
                    sources=[]
                )
            
            if not request.message or request.message.strip() == "":
                logger.info("Empty message detected. Returning fast acknowledgment.")
                return ChatResponse(
                    reply="I have successfully read your document. What would you like to know about it?",
                    sources=["System Acknowledgment"]
                )
        
        if not request.message or request.message.strip() == "":
            return ChatResponse(
                reply="How can I help you today?",
                sources=[]
            )
        
        result = generate_chat_response(
            message=request.message,
            session_id=request.session_id,
            project_id=request.project_id
        )
        return ChatResponse(reply=result["reply"], sources=result["sources"])
    
    except Exception as e:
        logger.error(f"Chatbot Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="The AI encountered an error processing your request.")