# Project_intelligence_hub/app/main.py
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat_router import router as chat_router
from app.api.lessons_router import router as lessons_router
from app.api.email_router import router as email_router
from app.api.project_analysis_router import router as project_analysis_router
from app.core.config import settings
from app.services.project_sync_scheduler import run_project_sync_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sync_task = None

    if settings.PROJECT_SYNC_AUTORUN:
        sync_task = asyncio.create_task(run_project_sync_scheduler())
        logger.info(
            "Project knowledge auto-sync enabled. Interval: %s seconds.",
            settings.PROJECT_SYNC_INTERVAL_SECONDS,
        )
    else:
        logger.info("Project knowledge auto-sync disabled.")

    try:
        yield
    finally:
        if sync_task:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                logger.info("Project knowledge auto-sync stopped.")


app = FastAPI(
    title="Project Intelligence Hub",
    description="Agentic RAG Microservice for PMO Insights",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(lessons_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(email_router, prefix="/api/v1")
app.include_router(project_analysis_router, prefix="/api/v1")

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Project Intelligence Hub"}
