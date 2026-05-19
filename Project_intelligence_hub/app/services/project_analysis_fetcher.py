import httpx

from app.core.config import settings


def _headers() -> dict:
    return {
        settings.BACKEND_SERVICE_HEADER_NAME: settings.BACKEND_SERVICE_TOKEN
    }


def _url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{settings.SOURCE_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


async def fetch_projects():
    url = settings.SOURCE_API_URL or _url(settings.GLOBAL_PROJECTS_PATH)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_headers())
        response.raise_for_status()
        return response.json()


async def fetch_project(project_id: str):
    path = settings.SINGLE_PROJECT_PATH.format(id=project_id)
    url = _url(path)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url, headers=_headers())
        response.raise_for_status()
        return response.json()