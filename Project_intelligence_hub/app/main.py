# Project_intelligence_hub/app/main.py
from fastapi import FastAPI
import logging
from fastapi.middleware.cors import CORSMiddleware
from app.api.lessons_router import router as lessons_router
from app.api.chat_router import router as chat_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Project Intelligence Hub",
    description="Agentic RAG Microservice for PMO Insights",
    version="1.0.0"
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

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Project Intelligence Hub"}