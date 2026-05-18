from typing import Optional

from pydantic import BaseModel, field_validator


class ProjectAnalysisChatRequest(BaseModel):
    question: str
    project_id: Optional[str] = None

    @field_validator("project_id", mode="before")
    @classmethod
    def normalize_placeholder_project_id(cls, value):
        if value is None:
            return None

        if isinstance(value, str) and value.strip().lower() in {"", "string", "null", "none"}:
            return None

        return value
