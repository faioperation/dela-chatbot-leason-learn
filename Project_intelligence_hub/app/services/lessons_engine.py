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
    # Fetch Live Project Data
    live_data = fetch_live_project_data(project_id)
    if not live_data:
        raise ValueError(f"Could not retrieve data for project {project_id}")
    
    # SAFETY FIX: Using 'or {}' ensures that if the API returns null/None, 
    # the code gets an empty dictionary instead of crashing.
    proj = live_data.get("project") or {}
    raidd_obj = live_data.get("raidd") or {}
    
    project_name = proj.get("name", "Unknown Project")
    project_desc = proj.get("description", "")
    
    current_phase = proj.get("status", "Unknown Phase") 
    
    meetings = proj.get("meetings") or []
    meeting_summaries = [m.get("lastMeetingSummary") for m in meetings if m.get("lastMeetingSummary")]
    
    # We use .get() safely on raidd_obj because we ensured it is at least an empty {} above
    raidd_type = raidd_obj.get('type', 'None')
    raidd_desc = raidd_obj.get('description', 'No active RAIDD issues reported.')

    dynamic_context = (
        f"Project Name: {project_name}\n"
        f"Description: {project_desc}\n"
        f"Status: {current_phase}\n"
        f"Progress: {proj.get('projectProgress', '0%')}\n"
        f"Backend AI Summary: {json.dumps(proj.get('projectAiSummary', []))}\n"
        f"Recent Meeting Notes: {json.dumps(meeting_summaries)}\n"
        f"Current RAIDD Flag: {raidd_type} - {raidd_desc}"
    )
    
    # Retrieve Historical Lessons from Pinecone using Global Index
    logger.info("Querying Pinecone for historical lessons...")
    if not GLOBAL_PINECONE_INDEX:
        raise ValueError("Pinecone index not initialized.")
    
    vector_store = PineconeVectorStore(pinecone_index=GLOBAL_PINECONE_INDEX, namespace="corporate_knowledge")
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    
    retriever = index.as_retriever(similarity_top_k=5)
    
    # Searching for historical lessons based on project description and current RAIDD issues
    query_str = f"Lessons learned, risks, and recommendations for projects involving: {project_desc} or facing issues like {raidd_desc}"
    retrieved_nodes = retriever.retrieve(query_str)
    
    # Exposing the metadata for citations
    historical_context = "\n\n".join([
        f"[Source: {n.metadata.get('source_file', 'Unknown')} - Row {n.metadata.get('row_index', 'N/A')}]\n{n.get_text()}" 
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