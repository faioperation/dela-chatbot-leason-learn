# Project_intelligence_hub/app/tools/vector_tools.py
import logging
from pinecone import Pinecone
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.pinecone import PineconeVectorStore
from llama_index.core.vector_stores.types import MetadataFilters, ExactMatchFilter
from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    GLOBAL_PINECONE_INDEX = pc.Index(settings.PINECONE_INDEX_NAME)
    logger.info("Pinecone connection pooled successfully in vector_tools.")
except Exception as e:
    logger.error(f"Failed to initialize Pinecone globally: {e}")
    GLOBAL_PINECONE_INDEX = None

def _perform_pinecone_search(query: str, namespace: str, top_k: int = 4) -> str:
    if not GLOBAL_PINECONE_INDEX:
        return "Error: Database connection not initialized."
        
    try:
        vector_store = PineconeVectorStore(pinecone_index=GLOBAL_PINECONE_INDEX, namespace=namespace)
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)
        
        if not nodes:
            return f"No relevant information found in the {namespace} database."
        
        results =[]
        for node in nodes:
            source = node.metadata.get('source_file', node.metadata.get('file_name', 'Unknown Source'))
            row_idx = node.metadata.get('row_index', '')
            row_str = f" - Row {row_idx}" if row_idx else ""
            
            results.append(f"[Source: {source}{row_str}]\n{node.get_text()}")
        
        return "\n\n".join(results)
    
    except Exception as e:
        logger.error(f"Vector search failed for namespace {namespace}: {e}")
        return "Error: Could not access the database at this time."

def search_project_documents(query: str) -> str:
    logger.info(f"Tool called: search_project_documents | Query: {query}")
    return _perform_pinecone_search(query, namespace="project_documents")

def search_corporate_knowledge(query: str) -> str:
    logger.info(f"Tool called: search_corporate_knowledge | Query: {query}")
    return _perform_pinecone_search(query, namespace="corporate_knowledge")

def search_email_templates(query: str) -> str:
    logger.info(f"Tool called: search_email_templates | Query: {query}")
    return _perform_pinecone_search(query, namespace="email_templates", top_k=5)

def get_dynamic_session_tool(session_id: str):
    """
    Creates a temporary tool scoped ONLY to this user's session.
    Prevents User A from reading User B's documents.
    """
    def search_my_uploaded_documents(query: str) -> str:
        """Searches documents that the user manually uploaded during this chat session."""
        logger.info(f"Tool called: search_my_uploaded_documents | Session: {session_id}")
        try:
            vector_store = PineconeVectorStore(pinecone_index=GLOBAL_PINECONE_INDEX, namespace="session_uploads")
            index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            
            # 🔥 SECURITY: Filter strictly by session_id
            filters = MetadataFilters(
                filters=[ExactMatchFilter(key="session_id", value=session_id)]
            )
            
            retriever = index.as_retriever(similarity_top_k=4, filters=filters)
            nodes = retriever.retrieve(query)
            
            if not nodes:
                return "No relevant information found in your uploaded documents."
                
            results = [f"[Source: Uploaded Document]\n{n.get_text()}" for n in nodes]
            return "\n\n".join(results)
        except Exception as e:
            logger.error(f"Session vector search failed: {e}")
            return "Error: Could not search uploaded documents."
    
    from llama_index.core.tools import FunctionTool
    return FunctionTool.from_defaults(
        fn=search_my_uploaded_documents,
        description="Use this tool ONLY when the user asks questions about a document, PDF, or file they just uploaded."
    )