from fastapi import APIRouter, Depends

from app.api.dependencies import verify_backend
from app.schemas.project_analysis_schemas import ProjectAnalysisChatRequest
from app.services.project_analysis_database import Base, engine, SessionLocal
from app.services.project_analysis_fact_cache import find_cached_answer
from app.services.project_chat_engine import answer_question, sync_project_knowledge


router = APIRouter(tags=["Project Analysis Chatbot"], dependencies=[Depends(verify_backend)])

Base.metadata.create_all(bind=engine)


@router.post("/sync")
async def sync_global():
    return await sync_project_knowledge()


@router.post("/sync/project/{project_id}")
async def sync_single_project(project_id: str):
    return await sync_project_knowledge(project_id=project_id)


@router.post("/chat")
def chat(request: ProjectAnalysisChatRequest):
    db = SessionLocal()

    try:
        cached = find_cached_answer(db, request.question)
        if cached and not request.project_id:
            return {
                "answer": cached["answer"],
                "sources": [{"type": cached["source"]}],
            }
    finally:
        db.close()

    return answer_question(request.question, project_id=request.project_id)


@router.post("/chat/project/{project_id}")
def chat_single_project(project_id: str, request: ProjectAnalysisChatRequest):
    return answer_question(request.question, project_id=project_id)
