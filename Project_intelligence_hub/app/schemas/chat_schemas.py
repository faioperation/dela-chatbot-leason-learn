# Project_intelligence_hub/app/schemas/chat_schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str

class ChatRequest(BaseModel):
    message: str = Field(default="", description="The user's current question")
    session_id: str = Field(..., description="Unique ID for this chat session")
    project_id: Optional[str] = Field(None, description="Optional: The current project they are viewing")
    document_url: Optional[str] = Field(None, description="Optional: Link to a PDF/DOCX file uploaded by the user")

class ChatResponse(BaseModel):
    reply: str
    sources: List[str]