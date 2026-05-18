from typing import Optional

from openai import OpenAI

from app.core.config import settings
from app.services.project_analysis_chunker import (
    chunk_full_json_payload,
    chunk_project_payload,
    normalize_payload,
)
from app.services.project_analysis_database import SessionLocal
from app.services.project_analysis_embeddings import create_embedding
from app.services.project_analysis_fact_cache import save_project_facts
from app.services.project_analysis_fetcher import fetch_project, fetch_projects
from app.services.project_analysis_pinecone import (
    delete_all_vectors,
    delete_project_vectors,
    search_similar,
    upsert_chunks,
)


CHAT_MODEL = "gpt-4.1-mini"

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def answer_identity_question(question: str) -> Optional[dict]:
    normalized = " ".join(question.lower().strip().split())
    identity_questions = {
        "who is this",
        "what is this",
        "who are you",
        "what are you",
        "introduce yourself",
    }

    if normalized in identity_questions or normalized.startswith(("who is this ", "what is this ")):
        return {
            "answer": (
                "I am a project analysis chatbot. I can help answer questions about synced project data, "
                "including project status, managers, tasks, meetings, risks, issues, assumptions, dependencies, "
                "decisions, and RAIDD insights."
            ),
            "sources": [],
        }

    return None


async def sync_project_knowledge(project_id: Optional[str] = None):
    payload = await fetch_project(project_id) if project_id else await fetch_projects()
    payload = normalize_payload(payload)

    db = SessionLocal()
    try:
        save_project_facts(db, payload)
    finally:
        db.close()

    chunks = chunk_project_payload(payload)
    chunks += chunk_full_json_payload(payload, max_lines=40)

    for chunk in chunks:
        chunk["embedding"] = create_embedding(chunk["text"])

    if project_id:
        delete_project_vectors(project_id)
    else:
        delete_all_vectors()

    upsert_chunks(chunks)

    return {
        "scope": "single" if project_id else "global",
        "project_id": project_id,
        "synced_chunks": len(chunks),
        "cached_facts": True,
    }


def answer_question(question: str, project_id: Optional[str] = None):
    identity_answer = answer_identity_question(question)
    if identity_answer:
        return identity_answer

    query_embedding = create_embedding(question)
    results = search_similar(query_embedding, top_k=12, project_id=project_id)
    matches = results.matches if hasattr(results, "matches") else results.get("matches", [])

    contexts = []
    for match in matches:
        metadata = match.metadata if hasattr(match, "metadata") else match.get("metadata", {})
        text = metadata.get("text", "")
        if text:
            contexts.append(text)

    if not contexts:
        return {
            "answer": "I don't have enough information in the project data to answer that. Please run sync first.",
            "sources": [],
        }

    context_text = "\n\n---\n\n".join(contexts)
    project_rule = (
        f"- Only answer for project_id {project_id}."
        if project_id
        else "- The context may contain multiple projects. Mention project names when useful."
    )

    prompt = f"""
You are a project data assistant.

Answer the user's question using ONLY the provided JSON context.

Rules:
- If the answer exists in the context, answer clearly.
- Understand this API shape: each item can contain project plus top-level raidd.
- The project name is found at project.name.
- RAIDD data can be found at raidd.aiDetection.raiddData and raidd.aiDetection.email.raiddData.
- If the user asks "what is the project name", answer from Project Name / project.name only.
- If there is one project in context, give only that project name.
- If there are multiple projects, list the project names.
- If the user asks about RAIDD, risks, assumptions, issues, dependencies, decisions, AI detection, source email, sentiment, tasks, meetings, manager, client, status, URL, or date, search the context carefully.
{project_rule}
- Do not use outside knowledge.
- Do not invent information.
- Keep the answer concise.

Context:
{context_text}

User question:
{question}
"""

    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You answer questions from synced project JSON data only.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.1,
    )

    return {
        "answer": response.choices[0].message.content,
        "sources": [
            match.metadata if hasattr(match, "metadata") else match.get("metadata", {})
            for match in matches
        ],
    }
