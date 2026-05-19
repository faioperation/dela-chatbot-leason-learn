import io
import logging
import re
import time
import uuid
import zipfile
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET

from fastapi import UploadFile
from pypdf import PdfReader

from app.services.project_analysis_embeddings import create_embedding
from app.services.project_analysis_pinecone import upsert_knowledge_chunks

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".pptx"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
CHUNK_SIZE = 1800
CHUNK_OVERLAP = 250
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "knowledge_base_uploads"


def _safe_filename(filename: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "knowledge_file")
    return cleaned.strip("._") or "knowledge_file"


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = []

    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n\n".join(pages)


def _extract_txt_text(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("latin-1", errors="ignore")


def _extract_text_from_xml(xml_bytes: bytes) -> str:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return ""

    text_parts = []

    for element in root.iter():
        tag = element.tag.split("}")[-1]

        if tag in {"t", "instrText"} and element.text:
            text_parts.append(element.text)
        elif tag in {"br", "cr", "tab"}:
            text_parts.append("\n")

    return " ".join(part.strip() for part in text_parts if part and part.strip())


def _extract_docx_text(content: bytes) -> str:
    xml_files = [
        "word/document.xml",
        *[f"word/header{i}.xml" for i in range(1, 10)],
        *[f"word/footer{i}.xml" for i in range(1, 10)],
    ]

    texts = []

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = set(archive.namelist())

        for name in xml_files:
            if name in names:
                texts.append(_extract_text_from_xml(archive.read(name)))

    return "\n\n".join(text for text in texts if text)


def _slide_sort_key(name: str):
    match = re.search(r"slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 0


def _extract_pptx_text(content: bytes) -> str:
    texts = []

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        slide_names = sorted(
            [
                name
                for name in archive.namelist()
                if name.startswith("ppt/slides/slide") and name.endswith(".xml")
            ],
            key=_slide_sort_key,
        )

        for slide_number, name in enumerate(slide_names, start=1):
            slide_text = _extract_text_from_xml(archive.read(name))

            if slide_text:
                texts.append(f"Slide {slide_number}: {slide_text}")

    return "\n\n".join(texts)


def _extract_text(filename: str, content: bytes) -> str:
    extension = Path(filename).suffix.lower()

    if extension == ".pdf":
        return _extract_pdf_text(content)

    if extension == ".txt":
        return _extract_txt_text(content)

    if extension == ".docx":
        return _extract_docx_text(content)

    if extension == ".pptx":
        return _extract_pptx_text(content)

    raise ValueError("Unsupported file type. Please upload a PDF, DOCX, TXT, or PPTX file.")


def _normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _chunk_text(text: str) -> list[str]:
    if not text:
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + CHUNK_SIZE, text_length)
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end == text_length:
            break

        start = max(end - CHUNK_OVERLAP, start + 1)

    return chunks


async def ingest_knowledge_base_file(
    file: UploadFile,
    *,
    project_id: Optional[str] = None,
    knowledge_base_id: Optional[str] = None,
) -> dict:
    original_filename = file.filename or "knowledge_file"
    safe_name = _safe_filename(original_filename)
    extension = Path(safe_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type. Please upload a PDF, DOCX, TXT, or PPTX file.")

    content = await file.read()

    if not content:
        raise ValueError("Uploaded file is empty.")

    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("Uploaded file is too large. Maximum allowed size is 25 MB.")

    knowledge_base_id = knowledge_base_id or str(uuid.uuid4())

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{knowledge_base_id}_{safe_name}"
    stored_path = UPLOAD_DIR / stored_filename
    stored_path.write_bytes(content)

    extracted_text = _normalize_text(_extract_text(safe_name, content))

    if not extracted_text:
        raise ValueError("Could not extract readable text from the uploaded file.")

    chunks = _chunk_text(extracted_text)

    if not chunks:
        raise ValueError("Could not create knowledge-base chunks from the uploaded file.")

    created_at = int(time.time())
    vector_chunks = []

    for index, chunk in enumerate(chunks):
        vector_chunks.append(
            {
                "id": f"kb:{knowledge_base_id}:{index}",
                "text": chunk,
                "embedding": create_embedding(chunk),
                "metadata": {
                    "knowledge_base_id": knowledge_base_id,
                    "project_id": project_id or "global",
                    "source_type": "knowledge_base_upload",
                    "source_file": safe_name,
                    "stored_file": stored_filename,
                    "chunk_index": index,
                    "created_at": created_at,
                },
            }
        )

    upsert_knowledge_chunks(vector_chunks)

    logger.info("Indexed %s knowledge-base chunks from %s", len(vector_chunks), safe_name)

    return {
        "knowledge_base_id": knowledge_base_id,
        "filename": safe_name,
        "stored_file": stored_filename,
        "project_id": project_id,
        "chunks_indexed": len(vector_chunks),
    }