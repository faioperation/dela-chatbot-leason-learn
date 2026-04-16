# Project_intelligence_hub/app/schemas/email_schemas.py
from typing import Optional
from pydantic import BaseModel, Field

class DraftReplyRequest(BaseModel):
    user_id: str                = Field(..., description="The ID of the user (to fetch their specific emails)")
    email_id: str               = Field(..., description="The ID of the email we are replying to.")
    instructions: Optional[str] = Field(None, description="Optional instructions from the user")

class DraftReplyLLM(BaseModel):
    subject: str                = Field(..., description="The subject line for the reply email")
    body: str                   = Field(..., description="The drafted email body, ready to be sent")
    tone_used: str              = Field(..., description="A brief explanation of the tone/style used")

class DraftReplyResponse(BaseModel):
    subject:    str
    body:       str
    tone_used:  str
    email_id:   str 