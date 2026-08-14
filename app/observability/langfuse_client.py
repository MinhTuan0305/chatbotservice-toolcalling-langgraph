"""
Langfuse client wrapper for LangGraph/LangChain integration.

Provides:
- get_langfuse_client() - singleton Langfuse client
- get_langfuse_handler() - CallbackHandler for LangChain/LangGraph
- is_langfuse_enabled() - check if Langfuse is configured
"""
import os
from typing import Optional

from langfuse import Langfuse
from langfuse.langchain import CallbackHandler


_langfuse_client: Optional[Langfuse] = None


def is_langfuse_enabled() -> bool:
    """Check if Langfuse credentials are configured."""
    host = os.getenv("LANGFUSE_HOST")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    
    # Check all are present and not placeholder values
    if not all([host, public_key, secret_key]):
        return False
    
    if public_key.startswith("...") or secret_key.startswith("..."):
        return False
    
    return True


def get_langfuse_client() -> Optional[Langfuse]:
    """
    Get singleton Langfuse client.
    
    Returns None if credentials not configured.
    """
    global _langfuse_client
    
    if not is_langfuse_enabled():
        return None
    
    if _langfuse_client is None:
        _langfuse_client = Langfuse(
            host=os.getenv("LANGFUSE_HOST"),
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        )
    
    return _langfuse_client


def get_langfuse_handler() -> Optional[CallbackHandler]:
    """
    Get Langfuse CallbackHandler for LangChain/LangGraph.
    
    SDK v4 LangChain integration: CallbackHandler() takes NO parameters.
    Trace attributes (session_id, user_id, metadata, tags) must be set via:
    - LangChain metadata in config (e.g., metadata={"langfuse_session_id": "..."})
    - OR propagate_attributes() context manager
    
    Returns:
        CallbackHandler if Langfuse enabled, None otherwise
    """
    if not is_langfuse_enabled():
        return None
    
    # LangChain CallbackHandler takes no constructor arguments
    handler = CallbackHandler()
    
    return handler


def flush_langfuse():
    """Flush pending Langfuse events (call on shutdown)."""
    client = get_langfuse_client()
    if client:
        client.flush()
