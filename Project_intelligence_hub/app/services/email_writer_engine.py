# Project_intelligence_hub/app/services/email_writer_engine.py
import logging
from openai import OpenAI
from pinecone import Pinecone
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from app.core.config import settings
from app.tools.api_tools import fetch_user_emails
from app.schemas.email_schemas import DraftReplyLLM, DraftReplyResponse

logger = logging.getLogger(__name__)
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def draft_email_reply(user_id: str, email_id: str, instructions: str = "") -> DraftReplyResponse:
    user_emails = fetch_user_emails(user_id)
    target_email = next((e for e in user_emails if e.get("id") == email_id), None)
    
    if not target_email:
        raise ValueError(f"Email with ID {email_id} not found for user {user_id}.")
    
    logger.info("Querying Pinecone for email writing templates...")
    try:
        pc = Pinecone(api_key=settings.PINECONE_API_KEY)
        vector_store = PineconeVectorStore(
            pinecone_index=pc.Index(settings.PINECONE_INDEX_NAME), 
            namespace="email_templates"
        )
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        retriever = index.as_retriever(similarity_top_k=3)
        
        retrieved_nodes = retriever.retrieve(f"How to reply to: {target_email.get('subject')}")
        style_context = "\n\n".join([n.get_text() for n in retrieved_nodes])
    except Exception as e:
        logger.warning(f"Could not retrieve style context from Pinecone: {e}. Proceeding with default tone.")
        style_context = "Use standard, professional corporate PMO tone."
    
    logger.info("Drafting reply with GPT-4o...")
    system_prompt = """
    You are an Expert PMO Communicator. Draft a professional email reply.
    You MUST adhere strictly to the rules and tone found in the 'Corporate Style Guide'.
    """
    
    user_prompt = f"""
    --- ORIGINAL EMAIL ---
    Subject: {target_email.get('subject')}
    From: {target_email.get('senderEmail')}
    Body: {target_email.get('body')}
    
    --- CORPORATE STYLE GUIDE (DOCX Rules & JSON Examples) ---
    {style_context}
    
    --- USER INSTRUCTIONS ---
    {instructions if instructions else "Acknowledge the email professionally."}
    
    Draft the reply.
    """
    
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format=DraftReplyLLM
        )
        
        ai_draft = completion.choices[0].message.parsed
        
        final_response = DraftReplyResponse(
            subject=ai_draft.subject,
            body=ai_draft.body,
            tone_used=ai_draft.tone_used,
            email_id=email_id
        )
        
        return final_response
    
    except Exception as e:
        logger.error(f"Failed to draft email: {e}", exc_info=True)
        raise e