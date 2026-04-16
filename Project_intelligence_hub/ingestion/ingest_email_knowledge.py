# Project_intelligence_hub/ingestion/ingest_email_templates.py
from typing import List
import sys, os, logging, json, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama_parse import LlamaParse
from pinecone import Pinecone, ServerlessSpec
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import Document, VectorStoreIndex, StorageContext, SimpleDirectoryReader
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def parse_json_emails(file_path: str) -> List[Document]:
    """Extracts writing examples from the JSON dataset."""
    logger.info(f"Parsing JSON templates from {file_path}")
    documents =[]
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        for email in data.get("emails",[]):
            metadata = email.get("metadata", {})
            text_content = (
                f"--- CORPORATE EMAIL WRITING EXAMPLE ---\n"
                f"Context / Project: {metadata.get('project', 'General')}\n"
                f"Subject: {metadata.get('subject', 'No Subject')}\n"
                f"Sender Role: {metadata.get('from', {}).get('role', 'PM')}\n"
                f"EMAIL BODY:\n{email.get('email_body', '')}\n"
            )
            documents.append(Document(
                text=text_content,
                metadata={"source_file": os.path.basename(file_path), "type": "writing_example"}
            ))
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
    return documents

def parse_docx_rules(file_path: str) -> List[Document]:
    """Uses LlamaParse to extract the 428-page DOCX writing rules."""
    logger.info(f"Parsing DOCX Rules from {file_path}")
    parser = LlamaParse(api_key=settings.LLAMA_CLOUD_API_KEY, result_type="markdown")
    try:
        reader = SimpleDirectoryReader(input_files=[file_path], file_extractor={".docx": parser})
        return reader.load_data()
    except Exception as e:
        logger.error(f"Failed to parse DOCX: {e}")
        return[]

def upload_to_email_namespace(documents: List[Document]):
    if not documents:
        return
    logger.info("Connecting to Pinecone...")
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index_name = settings.PINECONE_INDEX_NAME
    
    vector_store = PineconeVectorStore(pinecone_index=pc.Index(index_name), namespace="email_templates")
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    logger.info(f"Uploading {len(documents)} chunks to 'email_templates' namespace...")
    VectorStoreIndex.from_documents(documents, storage_context=storage_context, show_progress=True)
    logger.info("Upload Complete!")

if __name__ == "__main__":
    KB_DIR = os.path.join(os.path.dirname(__file__), "email_kb")
    json_path = os.path.join(KB_DIR, "pm_ai_training_data.json")
    docx_path = os.path.join(KB_DIR, "pm_ai_training_emails_200.docx")
    
    all_docs =[]
    if os.path.exists(json_path):
        all_docs.extend(parse_json_emails(json_path))
    if os.path.exists(docx_path):
        all_docs.extend(parse_docx_rules(docx_path))
    
    upload_to_email_namespace(all_docs)