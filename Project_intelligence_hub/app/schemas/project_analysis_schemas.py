from typing import Optional

from pydantic import BaseModel, Field, field_validator


PLACEHOLDER_VALUES = {"", "string", "null", "none", "dummy", "undefined"}


class ProjectAnalysisChatRequest(BaseModel):
    question: str = Field(default="", description="Question for the project-analysis chatbot")
    project_id: Optional[str] = Field(None, description="Optional project id for project-scoped chat")
    knowledge_base_id: Optional[str] = Field(
        None,
        description="Optional uploaded knowledge-base id. Leave null/blank/dummy when not using a file.",
    )

    @field_validator("project_id", "knowledge_base_id", mode="before")
    @classmethod
    def normalize_placeholder_ids(cls, value):
        if value is None:
            return None

        if isinstance(value, str) and value.strip().lower() in PLACEHOLDER_VALUES:
            return None

        return value