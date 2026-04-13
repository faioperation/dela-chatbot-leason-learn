# Project_intelligence_hub/ingestion/ingest_excel.py
import pandas as pd
from typing import List
import sys, os, logging, time, math
from pinecone import Pinecone, ServerlessSpec
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.config import settings
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core import Document, VectorStoreIndex, StorageContext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def process_single_excel_file(file_path: str) -> List[Document]:
    logger.info(f"📄 Processing file: {os.path.basename(file_path)}")
    documents =[]
    
    try:
        all_sheets = pd.read_excel(file_path, sheet_name=None)
        
        for sheet_name, df in all_sheets.items():
            logger.info(f"   -> Reading sheet: {sheet_name} ({len(df)} rows)")
            
            df = df.dropna(how='all')
            
            for index, row in df.iterrows():
                try:
                    row_text_parts =[]
                    for col_name, value in row.items():
                        if pd.isna(value) or str(value).strip() == "":
                            continue
                        
                        clean_col = str(col_name).strip()
                        clean_val = str(value).strip()
                        row_text_parts.append(f"{clean_col}: {clean_val}")
                    
                    # If the row had no usable text, skips
                    if not row_text_parts:
                        continue
                        
                    # Join the parts into a single descriptive paragraph
                    full_row_text = " | ".join(row_text_parts)
                    
                    metadata = {
                        "source_file": os.path.basename(file_path),
                        "sheet_name": str(sheet_name),
                        "row_index": index
                    }
                    
                    documents.append(Document(text=full_row_text, metadata=metadata))
                
                except Exception as row_error:
                    logger.warning(f"Skipping row {index} in {sheet_name} due to error: {row_error}")
                    continue
    
    except Exception as e:
        logger.error(f"Failed to process {file_path}: {e}")
    
    return documents


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
        namespace="corporate_knowledge" 
    )
    
    return StorageContext.from_defaults(vector_store=vector_store)


def batch_upload_documents(documents: List[Document], storage_context: StorageContext):
    if not documents:
        return
    
    logger.info(f"Uploading batch of {len(documents)} documents to Pinecone...")
    try:
        VectorStoreIndex.from_documents(
            documents, 
            storage_context=storage_context,
            show_progress=True 
        )
        logger.info(f"Uploaded {len(documents)} documents successfully.")
    except Exception as e:
        logger.error(f"Critical error during Pinecone upload: {e}")


def run_bulk_ingestion(directory_path: str):
    if not os.path.exists(directory_path):
        logger.error(f"Directory not found: {directory_path}")
        sys.exit(1)
    
    excel_files =[f for f in os.listdir(directory_path) if f.endswith(('.xlsx', '.xls', '.csv'))]
    
    if not excel_files:
        logger.warning(f"No Excel files found in {directory_path}")
        return
    
    logger.info(f"Found {len(excel_files)} Excel files. Starting bulk ingestion...")
    
    storage_context = get_pinecone_storage_context()
    
    for file_name in excel_files:
        full_path = os.path.join(directory_path, file_name)
        docs = process_single_excel_file(full_path)
        batch_upload_documents(docs, storage_context)
        time.sleep(1)
    
    logger.info("Bulk ingestion complete!")

if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    run_bulk_ingestion(DATA_DIR)