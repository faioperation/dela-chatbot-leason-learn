# Project_intelligence_hub/app/services/session_docs_engine.py
import logging, time
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from app.core.config import settings
from app.utils.file_handler import download_file_safely, cleanup_temp_file
from app.tools.vector_tools import GLOBAL_PINECONE_INDEX 

logger = logging.getLogger(__name__)

def process_session_document(document_url: str, session_id: str):
    """Downloads, parses, and upserts a user's session document to Pinecone."""
    local_filepath = None
    try:
        local_filepath = download_file_safely(document_url)
        
        reader = SimpleDirectoryReader(input_files=[local_filepath])
        documents = reader.load_data()
        
        if not documents:
            raise ValueError("Could not extract any text from the document.")
        
        expires_at = int(time.time()) + (7 * 24 * 60 * 60) 
        
        for doc in documents:
            doc.metadata["session_id"] = session_id
            doc.metadata["expires_at"] = expires_at
            doc.metadata["source"] = "user_upload"
        
        if not GLOBAL_PINECONE_INDEX:
            raise RuntimeError("Pinecone index not initialized.")
            
        vector_store = PineconeVectorStore(
            pinecone_index=GLOBAL_PINECONE_INDEX, 
            namespace="session_uploads"
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        
        VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=False
        )
        logger.info(f"✅ Successfully ingested session document for {session_id}")
    
    except Exception as e:
        logger.error(f"Session document processing failed: {e}")
        raise e
    
    finally:
        cleanup_temp_file(local_filepath)