from typing import Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.dependencies import verify_backend
from app.schemas.project_analysis_schemas import ProjectAnalysisChatRequest
from app.services.project_analysis_database import Base, engine, SessionLocal
from app.services.project_analysis_fact_cache import find_cached_answer
from app.services.project_analysis_knowledge_base import ingest_knowledge_base_file
from app.services.project_chat_engine import answer_question, sync_project_knowledge


router = APIRouter(tags=["Project Analysis Chatbot"], dependencies=[Depends(verify_backend)])

Base.metadata.create_all(bind=engine)


def _sync_error_response(exc: Exception):
    if isinstance(exc, httpx.HTTPStatusError):
        upstream_status = exc.response.status_code
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Project sync failed because the upstream project API returned an error.",
                "upstream_status": upstream_status,
                "upstream_url": str(exc.request.url),
            },
        ) from exc

    if isinstance(exc, httpx.RequestError):
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Project sync failed because the upstream project API could not be reached.",
                "upstream_url": str(exc.request.url) if exc.request else None,
            },
        ) from exc

    raise exc


@router.post("/sync")
async def sync_global():
    try:
        return await sync_project_knowledge()
    except Exception as exc:
        _sync_error_response(exc)


@router.post("/sync/project/{project_id}")
async def sync_single_project(project_id: str):
    try:
        return await sync_project_knowledge(project_id=project_id)
    except Exception as exc:
        _sync_error_response(exc)


async def _build_chat_request(
    raw_request: Request,
    *,
    form_question: Optional[str],
    form_project_id: Optional[str],
    form_knowledge_base_id: Optional[str],
    path_project_id: Optional[str] = None,
) -> ProjectAnalysisChatRequest:
    content_type = raw_request.headers.get("content-type", "").lower()

    if content_type.startswith("application/json"):
        try:
            payload = await raw_request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body.") from exc
    else:
        payload = {
            "question": form_question or "",
            "project_id": form_project_id,
            "knowledge_base_id": form_knowledge_base_id,
        }

    if path_project_id:
        payload["project_id"] = path_project_id

    return ProjectAnalysisChatRequest(**payload)


def _find_cached_project_answer(request: ProjectAnalysisChatRequest):
    if request.project_id or request.knowledge_base_id or not request.question.strip():
        return None

    db = SessionLocal()
    try:
        return find_cached_answer(db, request.question)
    finally:
        db.close()


@router.post("/chat")
async def chat(
    raw_request: Request,
    question: Optional[str] = Form(None, description="Question for the chatbot"),
    project_id: Optional[str] = Form(None, description="Optional project id. Can be blank/null/dummy."),
    knowledge_base_id: Optional[str] = Form(
        None,
        description="Optional existing knowledge-base id. Can be blank/null/dummy.",
    ),
    knowledge_file: Optional[UploadFile] = File(
        None,
        description="Optional PDF, DOCX, TXT, or PPTX file to save and use as a knowledge base.",
    ),
):
    request = await _build_chat_request(
        raw_request,
        form_question=question,
        form_project_id=project_id,
        form_knowledge_base_id=knowledge_base_id,
    )

    uploaded_knowledge = None

    if knowledge_file and knowledge_file.filename:
        try:
            uploaded_knowledge = await ingest_knowledge_base_file(
                knowledge_file,
                project_id=request.project_id,
                knowledge_base_id=request.knowledge_base_id,
            )
            request.knowledge_base_id = uploaded_knowledge["knowledge_base_id"]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not request.question.strip():
        if uploaded_knowledge:
            return {
                "answer": "Knowledge-base file uploaded and indexed successfully. Ask a question when you want to use it.",
                "knowledge_base": uploaded_knowledge,
                "sources": [],
            }

        raise HTTPException(
            status_code=400,
            detail="Question is required unless you are only uploading a knowledge-base file.",
        )

    cached = _find_cached_project_answer(request)

    if cached:
        return {
            "answer": cached["answer"],
            "knowledge_base": uploaded_knowledge,
            "sources": [{"type": cached["source"]}],
        }

    result = answer_question(
        request.question,
        project_id=request.project_id,
        knowledge_base_id=request.knowledge_base_id,
    )

    result["knowledge_base"] = uploaded_knowledge
    return result


@router.post("/chat/project/{project_id}")
async def chat_single_project(
    project_id: str,
    raw_request: Request,
    question: Optional[str] = Form(None, description="Question for the chatbot"),
    knowledge_base_id: Optional[str] = Form(
        None,
        description="Optional existing knowledge-base id. Can be blank/null/dummy.",
    ),
    knowledge_file: Optional[UploadFile] = File(
        None,
        description="Optional PDF, DOCX, TXT, or PPTX file to save and use as a knowledge base for this project.",
    ),
):
    request = await _build_chat_request(
        raw_request,
        form_question=question,
        form_project_id=None,
        form_knowledge_base_id=knowledge_base_id,
        path_project_id=project_id,
    )

    uploaded_knowledge = None

    if knowledge_file and knowledge_file.filename:
        try:
            uploaded_knowledge = await ingest_knowledge_base_file(
                knowledge_file,
                project_id=request.project_id,
                knowledge_base_id=request.knowledge_base_id,
            )
            request.knowledge_base_id = uploaded_knowledge["knowledge_base_id"]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not request.question.strip():
        if uploaded_knowledge:
            return {
                "answer": "Project knowledge-base file uploaded and indexed successfully. Ask a question when you want to use it.",
                "knowledge_base": uploaded_knowledge,
                "sources": [],
            }

        raise HTTPException(
            status_code=400,
            detail="Question is required unless you are only uploading a knowledge-base file.",
        )

    result = answer_question(
        request.question,
        project_id=request.project_id,
        knowledge_base_id=request.knowledge_base_id,
    )

    result["knowledge_base"] = uploaded_knowledge
    return result
