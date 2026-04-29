# Project_intelligence_hub/app/utils/file_handler.py
import os, requests, uuid, logging

logger = logging.getLogger(__name__)

TEMP_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "temp_uploads")
os.makedirs(TEMP_DIR, exist_ok=True)

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB limit

def download_file_safely(url: str) -> str:
    """
    Downloads a file from a URL, validates size and extension.
    Now supports PDF, DOCX, DOC, TXT, and PPTX.
    """
    logger.info(f"Downloading file from: {url}")
    
    # Extract file extension
    try:
        file_ext = url.split('.')[-1].split('?')[0].lower() # Handling URLs with query params
    except Exception:
        file_ext = 'pdf'

    # Added 'pptx' to the allowed list alongside current flow
    if file_ext not in ['pdf', 'docx', 'doc', 'txt', 'pptx']:
        logger.warning(f"Unsupported file extension '{file_ext}'. Falling back to 'pdf' logic.")
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
                            if os.path.exists(local_filepath):
                                os.remove(local_filepath) # Cleanup partial file
                            raise ValueError("The uploaded file exceeds the 5MB limit.")
                        f.write(chunk)
        
        logger.info(f"Successfully downloaded {file_ext} file to {local_filepath}")
        return local_filepath
        
    except Exception as e:
        if os.path.exists(local_filepath):
            os.remove(local_filepath)
        logger.error(f"Download failed: {e}")
        raise e

def cleanup_temp_file(filepath: str):
    """Deletes the temporary file after processing."""
    if filepath and os.path.exists(filepath):
        try:
            os.remove(filepath)
            logger.info(f"Cleaned up temp file: {filepath}")
        except Exception as e:
            logger.error(f"Failed to delete temp file {filepath}: {e}")