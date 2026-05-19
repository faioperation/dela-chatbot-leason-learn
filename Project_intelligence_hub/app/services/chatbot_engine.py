# Project_intelligence_hub/app/services/chatbot_engine.py
import logging, json
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import ReActAgent
from llama_index.core.llms import ChatMessage, MessageRole
from app.core.config import settings
from app.tools.api_tools import fetch_live_project_data
from app.tools.vector_tools import get_dynamic_session_tool

logger = logging.getLogger(__name__)

# In-memory store for chat histories keyed by session_id
_session_histories: dict = {}

def generate_chat_response(message: str, session_id: str, project_id: str = None) -> dict:
    llm = OpenAI(model="gpt-4o", api_key=settings.OPENAI_API_KEY)

    # Fetch live project data from backend
    live_data = fetch_live_project_data(project_id) if project_id else None

    # Build ground truth context string
    if live_data:
        proj       = live_data.get("project") or {}
        v_analysis = live_data.get("vendor_analysis") or {}
        raidd      = live_data.get("raidd") or {}

        ground_truth = (
            f"--- LIVE PROJECT DATA ---\n"
            f"Project Name: {proj.get('name')}\n"
            f"Health: {proj.get('projectHealth')}\n"
            f"Vendor: {proj.get('vendorName') or proj.get('vendor', {}).get('name')}\n"
            f"Vendor Portfolio: {v_analysis.get('risk_summary', 'No other projects found')}\n"
            f"Current RAIDD: {raidd.get('description', 'No specific issues logged')}\n"
            f"AI Flags: {json.dumps(proj.get('projectAiDetails', {}).get('raiddFlags', {}))}\n"
            f"--------------------------"
        )
    else:
        ground_truth = "Attention: No live data could be retrieved from the backend for this project ID."

    # System prompt injected as the first message in chat history
    SYSTEM_PROMPT = (
        f"You are the Strategic PMO Intelligence Engine.\n\n"
        f"YOUR TRUTH SOURCE:\n{ground_truth}\n\n"
        f"YOUR CAPABILITIES:\n"
        f"1. Analyze the LIVE DATA above. It is absolute fact.\n"
        f"2. Read uploaded PDF, PPTX, DOCX, and TXT files using the provided tool.\n"
        f"3. Always link RAIDD issues with the Vendor's performance.\n\n"
        f"If the user asks about the vendor, you MUST use the name and portfolio count from the LIVE DATA above."
    )

    # Build chat history for this session (prefix with system message)
    history = _session_histories.get(session_id, [])

    # ReActAgent does not accept system_prompt or memory directly.
    # We pass the system context as the first human/assistant exchange
    # so it is always visible in the conversation window.
    prefix_messages = [
        ChatMessage(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
    ]

    agent = ReActAgent.from_tools(
        tools=[get_dynamic_session_tool(session_id)],
        llm=llm,
        verbose=True,
        max_iterations=10,
        # Inject system context via prefix_messages
        prefix_messages=prefix_messages,
        # Pass accumulated history so the agent remembers prior turns
        chat_history=history,
    )

    # Run the agent
    response = agent.chat(message)

    # Persist updated history for next turn
    history.append(ChatMessage(role=MessageRole.USER,      content=message))
    history.append(ChatMessage(role=MessageRole.ASSISTANT, content=str(response)))

    # Keep history bounded to last 20 messages (~10 turns) to avoid token bloat
    _session_histories[session_id] = history[-20:]

    logger.info(f"Chat response generated for session {session_id}")

    return {
        "reply": str(response),
        "sources": ["Live Backend API", "Session Documents"] if live_data else ["Session Documents"],
    }