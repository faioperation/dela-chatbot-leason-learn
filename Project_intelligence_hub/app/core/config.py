# Project_intelligence_hub/app/core/config.py
import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# ১. পাথ ঠিক আছে কিনা নিশ্চিত করা
env_path = Path(__file__).resolve().parent.parent.parent / ".env"

# ২. .env ফাইল লোড করা
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
    print(f"✅ Configuration loaded successfully.")
    print(f"📂 Loaded from: {env_path}")
    print(f"🌐 API URL in use: {settings.PROJECTS_WITH_RAIDD_API}") # এই লাইনটি চেক করুন
except Exception as e:
    print(f"❌ ERROR: Environment validation failed.")
    print(f"Missing or Invalid Keys: {e}")
    raise e