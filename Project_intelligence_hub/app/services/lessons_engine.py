# Project_intelligence_hub/app/services/lessons_engine.py
import json, logging
from openai import OpenAI
from pinecone import Pinecone
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from app.core.config import settings
from app.tools.api_tools import fetch_live_project_data
from app.schemas.lessons_schemas import LessonsLearnedResponse

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

try:
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    GLOBAL_PINECONE_INDEX = pc.Index(settings.PINECONE_INDEX_NAME)
    logger.info("Pinecone connection pooled successfully in lessons_engine.")
except Exception as e:
    logger.error(f"Pinecone init failed in lessons_engine: {e}")
    GLOBAL_PINECONE_INDEX = None

def generate_lessons_learned(project_id: str) -> LessonsLearnedResponse:
    live_data = fetch_live_project_data(project_id)
    
    if not live_data:
        raise ValueError(f"The external backend API returned no data for project ID {project_id}.")
    
    try:
        proj = live_data.get("project") if isinstance(live_data.get("project"), dict) else {}
        raidd_obj = live_data.get("raidd") if isinstance(live_data.get("raidd"), dict) else {}
        
        if not proj and isinstance(live_data, dict) and "name" in live_data:
            proj = live_data
        
        project_name = proj.get("name") or "Unknown Project"
        project_desc = proj.get("description") or "No description provided."
        current_phase = proj.get("status") or "Unknown Phase" 
        
        meetings = proj.get("meetings")
        meeting_summaries =[]
        if isinstance(meetings, list):
            for m in meetings:
                if isinstance(m, dict) and m.get("lastMeetingSummary"):
                    meeting_summaries.append(m.get("lastMeetingSummary"))
        
        ai_summary = proj.get('projectAiSummary')
        if not isinstance(ai_summary, list):
            ai_summary =[]
            
        dynamic_context = (
            f"Project Name: {project_name}\n"
            f"Description: {project_desc}\n"
            f"Status: {current_phase}\n"
            f"Progress: {proj.get('projectProgress', '0%')}\n"
            f"Backend AI Summary: {json.dumps(ai_summary)}\n"
            f"Recent Meeting Notes: {json.dumps(meeting_summaries)}\n"
            f"Current RAIDD Flag: {raidd_obj.get('type', 'Unknown')} - {raidd_obj.get('description', 'None')}"
        )
        
    except Exception as e:
        logger.error(f"Failed to parse data from external API: {e}", exc_info=True)
        raise ValueError(f"Malformed data received from the main backend API. Details: {e}")
    
    logger.info("Querying Pinecone for historical lessons...")
    if not GLOBAL_PINECONE_INDEX:
        raise ValueError("Pinecone index not initialized.")
    
    vector_store = PineconeVectorStore(pinecone_index=GLOBAL_PINECONE_INDEX, namespace="corporate_knowledge")
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    
    retriever = index.as_retriever(similarity_top_k=5)
    query_str = f"Lessons learned, risks, and recommendations for projects involving: {project_desc}"
    retrieved_nodes = retriever.retrieve(query_str)
    
    historical_context = "\n\n".join([
        f"[Source: {(n.metadata or {}).get('source_file', 'Unknown')} - Row {(n.metadata or {}).get('row_index', 'N/A')}]\n{n.get_text()}" 
        for n in retrieved_nodes
    ])
    
    logger.info("Sending data to GPT-4o for synthesis...")
    
    system_prompt = f"""
    You are a Predictive PMO Intelligence Engine.
    You are helping a Project Manager who is currently in the '{current_phase}' phase/status of their project.
    
    CRITICAL INSTRUCTION: 
    For every Historical Insight you provide, you MUST cite the 'Source' found in the text. 
    Example: If the text says '[Source: lessons.xlsx - Row 402]', your source_evidence must be 'lessons.xlsx - Row 402'.
    
    Do NOT invent historical lessons. Only use the 'Historical Knowledge Base' provided.
    If the Current Live Project has active Risks or Issues, find historical data that shows how to solve them.
    """
    
    user_prompt = f"""
    --- CURRENT LIVE PROJECT ---
    {dynamic_context}
    
    --- HISTORICAL KNOWLEDGE BASE (Past Projects) ---
    {historical_context}
    
    Analyze the current project and map it to the historical lessons. Provide predictive warnings.
    """
    
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=LessonsLearnedResponse
        )
        
        result = completion.choices[0].message.parsed
        result.project_id = project_id
        result.project_name = project_name
        result.status = current_phase
        
        return result
    
    except Exception as e:
        logger.error(f"OpenAI generation failed: {e}", exc_info=True)
        raise e
