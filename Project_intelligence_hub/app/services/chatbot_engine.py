# Project_intelligence_hub/app/services/chatbot_engine.py
import logging
from llama_index.core.tools import FunctionTool
from llama_index.llms.openai import OpenAI
from llama_index.storage.chat_store.redis import RedisChatStore
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.agent.openai import OpenAIAgent
from app.core.config import settings
from app.tools.vector_tools import search_project_documents, search_corporate_knowledge
from app.tools.api_tools import fetch_live_project_data, fetch_all_emails, fetch_ai_detections

logger = logging.getLogger(__name__)

doc_search_tool = FunctionTool.from_defaults(
    fn=search_project_documents,
    description="Use this tool to search for exact text in uploaded project documents, contracts, PDFs, and meeting notes."
)

live_api_tool = FunctionTool.from_defaults(
    fn=fetch_live_project_data,
    description="Use this tool when the user asks about the CURRENT live status, tasks, health, or milestones of a project. Requires a project_id."
)

corporate_knowledge_tool = FunctionTool.from_defaults(
    fn=search_corporate_knowledge,
    description="Use this tool to search for historical project data, Excel records, KPIs, RAID logs, and past lessons learned."
)

email_tool = FunctionTool.from_defaults(
    fn=fetch_all_emails,
    description="Use this tool to read all system emails. Useful for finding latest communication and sentiment."
)

detection_tool = FunctionTool.from_defaults(
    fn=fetch_ai_detections,
    description="Use this tool to see previous AI detection logs, RAIDD analysis from emails, and task updates."
)

SYSTEM_PROMPT = """
You are the PMO Intelligence Assistant. You are an expert in project management.
You have access to a suite of tools:
- 'fetch_live_project_data': Use for current project health, RAIDD status, and tasks.
- 'search_project_documents': Use for contracts, PDFs, and meeting notes.
- 'search_corporate_knowledge': Use for the 13,000+ historical records and lessons learned.
- 'fetch_all_emails': Use to see recent email communications.
- 'fetch_ai_detections': Use to see historical RAIDD detections and identified patterns.

Always cite your sources, e.g., "According to the contract (Source: vendor_sow.pdf)..." or "The latest email suggests..."
If you cannot find an answer in the tools, state that you don't have that information.
"""

try:
    chat_store = RedisChatStore(redis_url=settings.REDIS_URL)
    logger.info("Redis Chat Store initialized successfully.")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    chat_store = None 

def generate_chat_response(message: str, session_id: str, project_id: str = None) -> dict:
    logger.info(f"Initializing ReAct Agentic Chatbot for Session: {session_id}...")
    
    llm = OpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY)
    
    context_msg = ""
    if project_id:
        context_msg = f" (Context: The user is currently viewing Project ID: {project_id})"
    
    memory = ChatMemoryBuffer.from_defaults(
        token_limit=3000,
        chat_store=chat_store,
        chat_store_key=session_id 
    )
    
    agent = OpenAIAgent.from_tools(
        tools=[doc_search_tool, corporate_knowledge_tool, live_api_tool, email_tool, detection_tool],
        llm=llm,
        memory=memory,  
        system_prompt=SYSTEM_PROMPT,
        verbose=True
    )
    
    response = agent.chat(message + context_msg)
    
    sources = ["Agent Tools"] if len(response.sources) > 0 else[]
    
    return {
        "reply": str(response),
        "sources": sources
    }