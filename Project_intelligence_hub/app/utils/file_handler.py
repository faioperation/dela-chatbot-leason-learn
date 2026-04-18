# Project_intelligence_hub/app/utils/file_handler.py
import os, requests, uuid, logging

logger = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp_uploads")
os.makedirs(TEMP_DIR, exist_ok=True)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

def download_file_safely(url: str) -> str:
    logger.info(f"Downloading file from: {url}")
    
    # Generate a random filename to prevent clashes
    file_ext = url.split('.')[-1].lower()
    if file_ext not in['pdf', 'docx', 'doc', 'txt']:
        file_ext = 'pdf' # Fallback
    
    local_filename = f"{uuid.uuid4()}.{file_ext}"
    local_filepath = os.path.join(TEMP_DIR, local_filename)
    
    downloaded_size = 0
    
    try:
        with requests.get(url, stream=True, timeout=15) as r:
            r.raise_for_status()
            with open(local_filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): 
                    if chunk:
                        downloaded_size += len(chunk)
                        if downloaded_size > MAX_FILE_SIZE_BYTES:
                            f.close()
                            os.remove(local_filepath) # Cleanup the partial file
                            raise ValueError("The uploaded file exceeds the 5MB limit.")
                        f.write(chunk)
        
        return local_filepath
    except Exception as e:
        if os.path.exists(local_filepath):
            os.remove(local_filepath)
        raise e

def cleanup_temp_file(filepath: str):
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
            logger.info(f"Cleaned up temp file: {filepath}")
        except Exception as e:
            logger.error(f"Failed to delete temp file {filepath}: {e}")