# Project_intelligence_hub/app/schemas/chat_schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

class ChatMessage(BaseModel):
    role: str                       = Field(..., description="'user' or 'assistant'")
    content: str

class ChatRequest(BaseModel):
    message: str                    = Field(..., description="The user's current question")
    project_id: Optional[str]       = Field(None, description="Optional: The current project they are viewing")
    chat_history: List[ChatMessage] = Field(default_factory=list)

class ChatResponse(BaseModel):
    reply: str                      = Field(..., description="The AI's conversational response")
    sources: List[str]              = Field(default_factory=list, description="Citations (e.g., PDF names or API endpoints)")