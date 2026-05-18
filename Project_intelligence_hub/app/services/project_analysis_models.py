from datetime import datetime

from sqlalchemy import Column, DateTime, String, Text

from app.services.project_analysis_database import Base


class ProjectFact(Base):
    __tablename__ = "project_facts"

    id = Column(String, primary_key=True)
    project_id = Column(String, index=True)
    project_name = Column(String, index=True)
    fact_type = Column(String, index=True)
    question_key = Column(String, index=True)
    answer = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow)
