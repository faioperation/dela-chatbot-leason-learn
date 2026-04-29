# Project_intelligence_hub/app/services/chatbot_engine.py
import logging, json
from llama_index.llms.openai import OpenAI
from llama_index.agent.openai import OpenAIAgent
from llama_index.core.memory import ChatMemoryBuffer
from app.core.config import settings
from app.tools.api_tools import fetch_live_project_data
from app.tools.vector_tools import get_dynamic_session_tool

def generate_chat_response(message: str, session_id: str, project_id: str = None) -> dict:
    llm = OpenAI(model="gpt-4o", api_key=settings.OPENAI_API_KEY)
    
    # ব্যাকএন্ড থেকে সরাসরি ডাটা ফেচ করা
    live_data = fetch_live_project_data(project_id) if project_id else None
    
    # এআই-কে দেওয়ার জন্য ডাটা ফরম্যাট করা
    if live_data:
        proj = live_data.get("project", {})
        v_analysis = live_data.get("vendor_analysis", {})
        raidd = live_data.get("raidd") or {}
        
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

    # এআই-এর জন্য কঠোর ইনস্ট্রাকশন (System Prompt)
    SYSTEM_PROMPT = f"""
    You are the Strategic PMO Intelligence Engine. Today is April 29, 2026.
    
    YOUR TRUTH SOURCE:
    {ground_truth}
    
    YOUR CAPABILITIES:
    1. Analyze the LIVE DATA above. It is absolute fact.
    2. Read uploaded PDF, PPTX, DOCX, and TXT files using the provided tool.
    3. Always link RAIDD issues with the Vendor's performance.
    
    If the user asks about the vendor, you MUST use the name and portfolio count from the LIVE DATA above.
    """

    # মেমরি এবং এজেন্ট সেটআপ
    memory = ChatMemoryBuffer.from_defaults(token_limit=3000, chat_store_key=session_id)
    
    agent = OpenAIAgent.from_tools(
        tools=[get_dynamic_session_tool(session_id)], # ফাইল রিডিংয়ের জন্য
        llm=llm, 
        memory=memory,
        system_prompt=SYSTEM_PROMPT,
        verbose=True
    )
    
    # এআই-কে দিয়ে প্রশ্নটি সলভ করানো
    response = agent.chat(message)
    
    return {
        "reply": str(response),
        "sources": ["Live Backend API", "Session Documents"] if live_data else ["Session Documents"]
    }