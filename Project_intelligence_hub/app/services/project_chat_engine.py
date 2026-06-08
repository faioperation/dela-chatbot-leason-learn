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
    search_knowledge_base,
    search_similar,
    upsert_chunks,
)


CHAT_MODEL = "gpt-4.1-mini"

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def _get_matches(results) -> list:
    return results.matches if hasattr(results, "matches") else results.get("matches", [])


def _get_metadata(match) -> dict:
    return match.metadata if hasattr(match, "metadata") else match.get("metadata", {})


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
                "decisions, RAIDD insights, and uploaded knowledge-base files."
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


def answer_question(
    question: str,
    project_id: Optional[str] = None,
    knowledge_base_id: Optional[str] = None,
):
    identity_answer = answer_identity_question(question)

    if identity_answer:
        return identity_answer

    query_embedding = create_embedding(question)

    project_results = search_similar(
        query_embedding,
        top_k=12,
        project_id=project_id,
    )
    project_matches = _get_matches(project_results)

    knowledge_results = search_knowledge_base(
        query_embedding,
        top_k=8,
        project_id=project_id,
        knowledge_base_id=knowledge_base_id,
    )
    knowledge_matches = _get_matches(knowledge_results)

    contexts = []

    for match in project_matches:
        metadata = _get_metadata(match)
        text = metadata.get("text", "")

        if text:
            contexts.append(f"[Synced Project Data]\n{text}")

    for match in knowledge_matches:
        metadata = _get_metadata(match)
        text = metadata.get("text", "")
        source_file = metadata.get("source_file", "Uploaded knowledge file")

        if text:
            contexts.append(f"[Knowledge Base: {source_file}]\n{text}")

    if not contexts:
        return {
            "answer": (
                "I don't have enough information in the synced project data or uploaded knowledge base to answer that. "
                "Please run sync first or upload a knowledge-base file."
            ),
            "sources": [],
        }

    context_text = "\n\n---\n\n".join(contexts)

    project_rule = (
        f"- Only answer for project_id {project_id}."
        if project_id
        else "- The synced project context may contain multiple projects. Mention project names when useful."
    )

    knowledge_rule = (
        f"- The user supplied knowledge_base_id {knowledge_base_id}; use it when the question is about uploaded files."
        if knowledge_base_id
        else "- Use uploaded knowledge-base context only when it is relevant to the question."
    )

    prompt = f"""
You are a project data assistant.

Answer the user's question using ONLY the provided context.

The context can contain two source types:
1. Synced Project Data: JSON-derived project, RAIDD, task, meeting, risk, issue, dependency, decision, and email data.
2. Knowledge Base: text extracted from a user-uploaded PDF, DOCX, TXT, or PPTX file.

Rules:
- If the answer exists in the context, answer clearly.
- Understand this API shape: each item can contain project plus top-level raidd.
- The project name is found at project.name.
- RAIDD data can be found at raidd.aiDetection.raiddData and raidd.aiDetection.email.raiddData.
- If the user asks "what is the project name", answer from Project Name / project.name only.
- If the user asks who the project owner is, resolve Project Owner ID/projectOwnerId to the matching person in context when possible. If projectOwnerId matches manager.id/Manager ID, answer with the manager's full name and role, and optionally include the ID only as supporting detail.
- For any "who is" question about owner, manager, creator, client, contact, assignee, or team, prefer human-readable names, roles, emails, and team names from related objects over raw IDs.
- Return a raw ID only when no matching human-readable object or name is available in the context.
- If there is one project in context, give only that project name.
- If there are multiple projects, list the project names.
- If the user asks about RAIDD, risks, assumptions, issues, dependencies, decisions, AI detection, source email, sentiment, tasks, meetings, manager, client, status, URL, or date, search the context carefully.
- For RAIDD count questions, use top-level project raidd records as the canonical count source.
- Count a RAIDD record as a risk when its RAIDD Type/type array contains "RISK", even if the same record also contains ISSUE, ASSUMPTION, DEPENDENCY, or DECISION.
- Treat RAIDD Status/status values of null, empty, unknown, OPEN, or IN_PROGRESS as open/unresolved. Treat only explicit closed states such as CLOSED, RESOLVED, DONE, CANCELLED, or DELETED as not open.
- Do not count nested aiDetection.raiddData/projectRisks/email projectRisks as additional separate risks when they belong to a top-level RAIDD record; use them only to describe the risk details.
- If the user asks for a report, status report, full status report, project report, or summary report, format the answer as a structured Markdown report instead of a long paragraph.
- For report-style answers, use these sections when the information is available: Executive Summary, Project Overview, Timeline, Health and Progress, Client, Project Manager, Team, Key Discussion Points, Action Points, Tasks, RAIDD Summary, Meetings, Decisions Needed, and Overall Summary.
- For report-style answers, use short bullets or compact tables under each section, keep related facts grouped together, and write "Not available in context" for important missing report fields instead of inventing them.
- Format all dates in your answer strictly as "Month Day, Year" (e.g., "January 1, 2026"). Do not use "YYYY-MM-DD", "YYYY-M-D", or relative dates unless quoting the exact text verbatim.
{project_rule}
{knowledge_rule}
- Do not use outside knowledge.
- Do not invent information.
- If project data and knowledge-base data conflict, mention the conflict instead of choosing silently.
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
                "content": "You answer questions from synced project data and uploaded knowledge-base context only.",
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
            *_get_source_list(project_matches, "project_data"),
            *_get_source_list(knowledge_matches, "knowledge_base"),
        ],
    }


def _get_source_list(matches: list, default_type: str) -> list[dict]:
    sources = []

    for match in matches:
        metadata = _get_metadata(match)
        metadata.setdefault("type", default_type)
        sources.append(metadata)

    return sources
