from typing import Optional

from pinecone.exceptions import NotFoundException
from pinecone import Pinecone

from app.core.config import settings


PROJECT_ANALYSIS_NAMESPACE = "project_analysis"

pc = Pinecone(api_key=settings.PINECONE_API_KEY)
index = pc.Index(settings.PINECONE_INDEX_NAME)


def _ignore_missing_namespace(error: NotFoundException):
    body = getattr(error, "body", "") or str(error)
    if "Namespace not found" not in body:
        raise error


def clean_metadata(metadata: dict) -> dict:
    cleaned = {}

    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        elif isinstance(value, list):
            cleaned[key] = [str(item) for item in value if item is not None]
        else:
            cleaned[key] = str(value)

    return cleaned


def delete_all_vectors():
    try:
        index.delete(delete_all=True, namespace=PROJECT_ANALYSIS_NAMESPACE)
    except NotFoundException as exc:
        _ignore_missing_namespace(exc)


def delete_project_vectors(project_id: str):
    try:
        index.delete(
            namespace=PROJECT_ANALYSIS_NAMESPACE,
            filter={"project_id": {"$eq": project_id}},
        )
    except NotFoundException as exc:
        _ignore_missing_namespace(exc)


def upsert_chunks(chunks, batch_size=50):
    vectors = []

    for chunk in chunks:
        metadata = {
            **chunk.get("metadata", {}),
            "text": chunk.get("text", ""),
        }
        vectors.append({
            "id": chunk["id"],
            "values": chunk["embedding"],
            "metadata": clean_metadata(metadata),
        })

    for i in range(0, len(vectors), batch_size):
        index.upsert(vectors=vectors[i:i + batch_size], namespace=PROJECT_ANALYSIS_NAMESPACE)


def search_similar(query_embedding, top_k=5, project_id: Optional[str] = None):
    query = {
        "namespace": PROJECT_ANALYSIS_NAMESPACE,
        "vector": query_embedding,
        "top_k": top_k,
        "include_metadata": True,
    }

    if project_id:
        query["filter"] = {"project_id": {"$eq": project_id}}

    return index.query(**query)
