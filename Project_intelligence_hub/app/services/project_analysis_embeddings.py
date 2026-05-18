from openai import OpenAI

from app.core.config import settings


EMBEDDING_MODEL = "text-embedding-3-small"

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def create_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding
