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

def generate_lessons_learned(project_id: str) -> LessonsLearnedResponse:
    live_data = fetch_live_project_data(project_id)
    
    if not live_data:
        raise ValueError(f"Could not retrieve data for project {project_id}")
    
    # Safely extract the nested objects
    proj = live_data.get("project", {})
    raidd_obj = live_data.get("raidd", {})
    
    project_name = proj.get("name", "Unknown Project")
    project_desc = proj.get("description", "")
    
    # Safely extract meeting summaries if exist
    meetings = proj.get("meetings", [])
    meeting_summaries =[m.get("lastMeetingSummary") for m in meetings if m.get("lastMeetingSummary")]
    
    # Build a highly detailed dynamic context
    dynamic_context = (
        f"Project Name: {project_name}\n"
        f"Description: {project_desc}\n"
        f"Status: {proj.get('status')}\n"
        f"Progress: {proj.get('projectProgress', '0%')}\n"
        f"Backend AI Summary: {json.dumps(proj.get('projectAiSummary',[]))}\n"
        f"Recent Meeting Notes: {json.dumps(meeting_summaries)}\n"
        f"Current RAIDD Flag: {raidd_obj.get('type')} - {raidd_obj.get('description', 'None')}"
    )
    
    logger.info("Querying Pinecone for historical lessons...")
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    pinecone_index = pc.Index(settings.PINECONE_INDEX_NAME)
    
    vector_store = PineconeVectorStore(pinecone_index=pinecone_index, namespace="corporate_knowledge")
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    
    # Fetch top 5 historical lessons to give maximum breadth
    retriever = index.as_retriever(similarity_top_k=5)
    
    # Query using the rich AI Summary and description
    query_str = f"Lessons learned, risks, and recommendations for projects involving: {project_desc} or facing issues like {raidd_obj.get('description', '')}"
    retrieved_nodes = retriever.retrieve(query_str)
    
    historical_context = "\n\n".join([
        f"[Source File: {n.metadata.get('source_file', 'Unknown')}, Row Index: {n.metadata.get('row_index', 'Unknown')}]\n{n.get_text()}" 
        for n in retrieved_nodes
    ])
    
    # Synthesize with GPT-4o
    logger.info("Sending data to GPT-4o for synthesis...")
    
    system_prompt = """
    You are a Senior PMO Mentor. You are helping a Project Manager who is currently in the '{current_phase}' of their project.
    
    TASK:
    1. Compare the 'Live Project Data' with the 'Historical Knowledge Base'.
    2. Identify specific 'Expectation vs. Reality' gaps from the past that apply here.
    3. Focus on Wale's criteria: Vendor timelines, security requirements, and resource bottlenecks.
    
    Example logic: 
    If the historical data says 'Vendor material took 3 weeks instead of 2', and the current project is 'Planning', warn the PM to allocate 3 weeks now to avoid future delays.
    
    Provide actionable recommendations and cite the source file.
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
        result.status = proj.get('status', 'UNKNOWN')
        
        return result
    
    except Exception as e:
        logger.error(f"OpenAI generation failed: {e}", exc_info=True)
        raise e