# Project_intelligence_hub/ingestion/ingest_documents.py
import sys, os, logging, time, json
from typing import List
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llama_parse import LlamaParse
from pinecone import Pinecone, ServerlessSpec
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import VectorStoreIndex, StorageContext, SimpleDirectoryReader
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


TRACKER_FILE = os.path.join(os.path.dirname(__file__), "ingested_files_tracker.json")

def load_tracker() -> dict:
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_tracker(data: dict):
    with open(TRACKER_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_pinecone_storage_context():
    logger.info("Connecting to Pinecone...")
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    index_name = settings.PINECONE_INDEX_NAME
    
    existing_indexes = [index_info["name"] for index_info in pc.list_indexes()]
    if index_name not in existing_indexes:
        logger.warning(f"Index '{index_name}' not found. Creating it now...")
        pc.create_index(
            name=index_name,
            dimension=1536, 
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region=settings.PINECONE_ENV)
        )
        while not pc.describe_index(index_name).status['ready']:
            time.sleep(2)
        logger.info(f"Index '{index_name}' created successfully!")
    
    pinecone_index = pc.Index(index_name)
    
    vector_store = PineconeVectorStore(
        pinecone_index=pinecone_index, 
        namespace="project_documents" 
    )
    
    return StorageContext.from_defaults(vector_store=vector_store)


def run_bulk_document_ingestion(directory_path: str):
    if not os.path.exists(directory_path):
        logger.error(f"Directory not found: {directory_path}")
        sys.exit(1)
        
    parser = LlamaParse(
        api_key=settings.LLAMA_CLOUD_API_KEY,
        result_type="markdown",
        verbose=False 
    )
    
    file_extractor = {
        ".pdf": parser, 
        ".docx": parser,
        ".doc": parser,
        ".pptx": parser,
        ".ppt": parser
    }
    
    all_files =[]
    for root, _, files in os.walk(directory_path):
        for f in files:
            if f.lower().endswith(('.pdf', '.docx', '.doc', '.pptx', '.ppt', '.txt')):
                all_files.append(os.path.join(root, f))
    
    if not all_files:
        logger.warning(f"No supported documents found in {directory_path}")
        return
    
    tracker = load_tracker()
    
    storage_context = get_pinecone_storage_context()
    
    processed_count = 0
    skipped_count = 0
    
    logger.info(f"Found {len(all_files)} total documents in directory.")
    
    for file_path in all_files:
        file_name = os.path.basename(file_path)
        
        # Check Last Modified Timestamp
        current_mtime = os.path.getmtime(file_path)
        
        # INCREMENTAL CHECK: Is it already done and unchanged?
        if file_path in tracker and tracker[file_path] == current_mtime:
            logger.info(f"Skipping: {file_name} (Already ingested and unchanged).")
            skipped_count += 1
            continue
            
        logger.info(f"Processing: {file_name} (New or Modified)")
        
        try:
            reader = SimpleDirectoryReader(
                input_files=[file_path],
                file_extractor=file_extractor
            )
            documents = reader.load_data()
            
            if not documents:
                logger.warning(f"No text extracted from {file_name}. Skipping.")
                continue
            
            logger.info(f"   -> Uploading {len(documents)} chunks to Pinecone...")
            VectorStoreIndex.from_documents(
                documents, 
                storage_context=storage_context,
                show_progress=False 
            )
            logger.info(f"   Success: {file_name}")
            
            tracker[file_path] = current_mtime
            save_tracker(tracker)
            processed_count += 1
            
            time.sleep(2) # Rate limit protection
        
        except Exception as e:
            logger.error(f"Failed to process {file_name}: {e}")
            continue
        
    logger.info(f"Ingestion Run Complete! Processed: {processed_count} | Skipped: {skipped_count}")

if __name__ == "__main__":
    DOCS_DIR = os.path.join(os.path.dirname(__file__), "docs")
    run_bulk_document_ingestion(DOCS_DIR)