# Project_intelligence_hub/app/core/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    LLAMA_CLOUD_API_KEY: str = "" 
    
    PINECONE_API_KEY: str
    PINECONE_ENV: str
    PINECONE_INDEX_NAME: str
    
    PROJECTS_WITH_RAIDD_API: str
    SINGLE_PROJECT_API: str
    AI_DETECTION_API: str
    ALL_EMAILS_API: str
    
    REDIS_URL: str = "redis://localhost:6379/0"
    
    model_config = SettingsConfigDict(extra="ignore")

try:
    settings = Settings()
    print("Configuration loaded successfully.")
except Exception as e:
    print(f"ERROR: Environment validation failed. Missing keys in .env file.")
    raise e