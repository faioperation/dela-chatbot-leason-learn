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


def _extract_project_dict(live_data: dict) -> dict:
    """
    Safely extracts the project dict from live_data regardless of shape.
    Handles these real-world variants:
      - live_data["project"] = { ... }           (normal dict)
      - live_data["project"] = [ { ... } ]       (list with one item)
      - live_data itself is the project dict      (flat structure)
    """
    raw = live_data.get("project")

    if isinstance(raw, dict):
        return raw

    if isinstance(raw, list) and len(raw) > 0:
        first = raw[0]
        if isinstance(first, dict):
            return first

    # Fallback: live_data itself may be the project object
    if "name" in live_data or "status" in live_data:
        return live_data

    logger.warning("Could not extract project dict from live_data — returning empty dict")
    return {}


def _extract_raidd_dict(live_data: dict) -> dict:
    """
    Safely extracts the raidd dict from live_data regardless of shape.
    """
    raw = live_data.get("raidd")

    if isinstance(raw, dict):
        return raw

    if isinstance(raw, list) and len(raw) > 0:
        first = raw[0]
        if isinstance(first, dict):
            return first

    return {}


def generate_lessons_learned(project_id: str) -> LessonsLearnedResponse:
    # Fetch Live Project Data
    live_data = fetch_live_project_data(project_id)
    if not live_data:
        raise ValueError(f"Could not retrieve data for project {project_id}")

    logger.info(f"live_data keys: {list(live_data.keys())}")

    # Robustly extract project and raidd regardless of API shape
    proj     = _extract_project_dict(live_data)
    raidd_obj = _extract_raidd_dict(live_data)

    logger.info(f"Extracted project keys: {list(proj.keys()) if proj else 'EMPTY'}")

    project_name = proj.get("name", "Unknown Project")
    project_desc = proj.get("description", "")
    current_phase = proj.get("status", "Unknown Phase")

    meetings = proj.get("meetings") or []
    if isinstance(meetings, list):
        meeting_summaries = [
            m.get("lastMeetingSummary")
            for m in meetings
            if isinstance(m, dict) and m.get("lastMeetingSummary")
        ]
    else:
        meeting_summaries = []

    raidd_type = raidd_obj.get("type", "None")
    raidd_desc = raidd_obj.get("description", "No active RAIDD issues reported.")

    dynamic_context = (
        f"Project Name: {project_name}\n"
        f"Description: {project_desc}\n"
        f"Status: {current_phase}\n"
        f"Progress: {proj.get('projectProgress', '0%')}\n"
        f"Backend AI Summary: {json.dumps(proj.get('projectAiSummary', []))}\n"
        f"Recent Meeting Notes: {json.dumps(meeting_summaries)}\n"
        f"Current RAIDD Flag: {raidd_type} - {raidd_desc}"
    )

    # Retrieve Historical Lessons from Pinecone
    logger.info("Querying Pinecone for historical lessons...")
    if not GLOBAL_PINECONE_INDEX:
        raise ValueError("Pinecone index not initialized.")

    vector_store = PineconeVectorStore(
        pinecone_index=GLOBAL_PINECONE_INDEX,
        namespace="corporate_knowledge"
    )
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
    retriever = index.as_retriever(similarity_top_k=5)

    query_str = (
        f"Lessons learned, risks, and recommendations for projects involving: "
        f"{project_desc} or facing issues like {raidd_desc}"
    )
    retrieved_nodes = retriever.retrieve(query_str)

    historical_context = "\n\n".join([
        f"[Source: {n.metadata.get('source_file', 'Unknown')} - Row {n.metadata.get('row_index', 'N/A')}]\n{n.get_text()}"
        for n in retrieved_nodes
    ])

    if not historical_context.strip():
        historical_context = "No historical lessons found in the knowledge base."

    logger.info("Sending data to GPT-4o for synthesis...")

    system_prompt = f"""
You are a Predictive PMO Intelligence Engine.
You are helping a Project Manager who is currently in the '{current_phase}' phase/status of their project.

CRITICAL INSTRUCTION:
For every Historical Insight you provide, you MUST cite the 'Source' found in the text.
Example: If the text says '[Source: lessons.xlsx - Row 402]', your source_evidence must be 'lessons.xlsx - Row 402'.

Do NOT invent historical lessons. Only use the 'Historical Knowledge Base' provided.
If the Current Live Project has active Risks or Issues, find historical data that shows how to solve them.
If no historical data is available, still provide a helpful summary and leave historical_insights as an empty list.
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
                {"role": "user",   "content": user_prompt}
            ],
            response_format=LessonsLearnedResponse
        )

        result = completion.choices[0].message.parsed
        result.project_id   = project_id
        result.project_name = project_name
        result.status       = current_phase

        return result

    except Exception as e:
        logger.error(f"OpenAI generation failed: {e}", exc_info=True)
        raise e