import asyncio
import httpx

from app.core.config import settings


TRANSIENT_STATUS_CODES = {502, 503, 504}
MAX_FETCH_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 2


def _headers() -> dict:
    return {
        settings.BACKEND_SERVICE_HEADER_NAME: settings.BACKEND_SERVICE_TOKEN
    }


def _url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{settings.SOURCE_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def _single_project_url(project_id: str) -> str:
    if not settings.SINGLE_PROJECT_API:
        return _url(settings.SINGLE_PROJECT_PATH.format(id=project_id))

    if "{id}" in settings.SINGLE_PROJECT_API or "{project_id}" in settings.SINGLE_PROJECT_API:
        return settings.SINGLE_PROJECT_API.format(id=project_id, project_id=project_id)

    return f"{settings.SINGLE_PROJECT_API.rstrip('/')}/{project_id}"


async def fetch_projects():
    url = settings.SOURCE_API_URL or settings.PROJECTS_WITH_RAIDD_API or _url(settings.GLOBAL_PROJECTS_PATH)
    return await _get_json(url)


async def _get_json(url: str):
    last_error = None

    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
            try:
                response = await client.get(url, headers=_headers())
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code

                if status_code not in TRANSIENT_STATUS_CODES or attempt == MAX_FETCH_ATTEMPTS:
                    raise

            await asyncio.sleep(RETRY_DELAY_SECONDS * attempt)

    if last_error:
        raise last_error


async def fetch_project(project_id: str):
    return await _get_json(_single_project_url(project_id))
