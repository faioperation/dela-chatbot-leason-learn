# Project_intelligence_hub/app/schemas/lessons_schemas.py
from typing import List
from pydantic import BaseModel, Field

# REQUEST SCHEMA 
class LessonsRequest(BaseModel):
    project_id: str             = Field(..., description="The UUID of the live project to analyze")

# RESPONSE SCHEMAS
class HistoricalInsight(BaseModel):
    relevance: str              = Field(..., description="'High', 'Medium', or 'Low'")
    historical_lesson: str      = Field(..., description="The lesson extracted from past projects")
    source_project_type: str    = Field(..., description="The industry or type of the past project")
    recommendation_for_current_project: str = Field(..., description="Actionable advice for the current project")
    source_evidence: str        = Field(..., description="The name of the file or project this lesson was pulled from.")

class LessonsLearnedResponse(BaseModel):
    project_id: str
    project_name: str
    status: str
    current_situation_summary: str = Field(..., description="A 2-3 sentence summary of the current live project")
    historical_insights: List[HistoricalInsight]
    actionable_warnings: List[str] = Field(..., description="Predictive warnings based on past failures")