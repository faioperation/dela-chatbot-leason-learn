# Project_intelligence_hub/app/core/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the project-level .env path.
env_path = Path(__file__).resolve().parent.parent.parent / ".env"

# Load environment variables from .env.
load_dotenv(dotenv_path=env_path)

class Settings(BaseSettings):
    # AI & Vector DB Keys
    OPENAI_API_KEY: str
    LLAMA_CLOUD_API_KEY: str = "" 
    
    PINECONE_API_KEY: str
    PINECONE_ENV: str
    PINECONE_INDEX_NAME: str
    
    # PMIFY Backend APIs
    PROJECTS_WITH_RAIDD_API: str
    SINGLE_PROJECT_API: str
    AI_DETECTION_API: str
    USER_EMAILS_API: str
    ALL_EMAILS_API: str
    ALL_USERS_API: str
    SOURCE_API_BASE_URL: str = "https://accustomed-maryalice-bubbleless.ngrok-free.dev/api"
    GLOBAL_PROJECTS_PATH: str = "/project/all/with-raidd/chatbot"
    SINGLE_PROJECT_PATH: str = "/project/with-raidd/chatbot/{id}"
    SOURCE_API_URL: str = ""
    SOURCE_API_TOKEN: str = ""
    BACKEND_SERVICE_HEADER_NAME: str = "x-backend-service"
    BACKEND_SERVICE_TOKEN: str
    PROJECT_SYNC_AUTORUN: bool = True
    PROJECT_SYNC_GLOBAL_AUTORUN: bool = True
    PROJECT_SYNC_PROJECT_IDS: str = ""
    PROJECT_SYNC_INTERVAL_SECONDS: int = 3600

    model_config = SettingsConfigDict(
        env_file=str(env_path),
        extra="ignore",
    )
    
    # Auth Token
    BACKEND_API_TOKEN: str
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Pydantic Settings Configuration
    model_config = SettingsConfigDict(
        env_file=str(env_path),
        extra="ignore"
    )

try:
    settings = Settings()
    print("Configuration loaded successfully.")
    print(f"Loaded from: {env_path}")
    print(f"API URL in use: {settings.PROJECTS_WITH_RAIDD_API}")
except Exception as e:
    print("ERROR: Environment validation failed.")
    print(f"Missing or Invalid Keys: {e}")
    raise e
