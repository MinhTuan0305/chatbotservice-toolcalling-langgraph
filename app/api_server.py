"""
AI Agent API Server (FastAPI)

Standalone service that owns the LangGraph agent (LLM, tools, checkpointer).
It has no knowledge of Socket.IO / rooms / connected clients — that is the
Socket Service's job (app/socket_server.py). The Socket Service talks to
this service over HTTP to get chat responses.

Runs on its own port (API_PORT, default 8000), independent from the
Socket Service (SOCKET_PORT, default 5000), so each can be deployed and
scaled separately.
"""

import json
import logging
import os
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.service import ChatService
from app.config import (
    API_HOST, API_PORT, API_LOG_FILE, CORS_ORIGINS,
    API_KEY, LOG_LEVEL,
)
from app.observability.langfuse_client import is_langfuse_enabled

# ─────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────

os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(API_LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 5000

app = FastAPI(
    title="Shop Chatbot AI Agent Service",
    version="1.0.0",
)

cors_origins = [CORS_ORIGINS] if CORS_ORIGINS != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single shared instance, thread-safe across requests (mirrors socket_server)
chat_service = ChatService()


# ─────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    thread_id: str = Field(..., min_length=1, max_length=100)
    tool_enabled: Optional[bool] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None


class ChatResponse(BaseModel):
    final_answer: str
    tool_calls: list
    thread_id: str


# ─────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────

def require_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Verify the internal service-to-service API key.

    NOTE: this is a placeholder until JWT auth (shared with the Socket
    Service) is wired in. For now it just gates access to this service
    the same way socket_server.py gates /health and /stats.
    """
    if not API_KEY:
        logger.warning("API_KEY not configured - api_server is unprotected")
        return
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid API key required",
        )


def sanitize_thread_id(thread_id: str) -> str:
    """Allow only alphanumeric, dash, underscore; cap length at 100 chars."""
    import re
    return re.sub(r'[^a-zA-Z0-9\-_]', '', thread_id)[:100]


# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "shop-chatbot-agent",
        "version": "1.0.0",
        "langfuse_enabled": is_langfuse_enabled(),
    }


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, x_api_key: Optional[str] = Header(None)):
    require_api_key(x_api_key)

    thread_id = sanitize_thread_id(payload.thread_id)
    if not thread_id:
        raise HTTPException(status_code=400, detail="Invalid thread_id format")

    tool_enabled = payload.tool_enabled if payload.tool_enabled is not None else True

    logger.info(f"Processing message for thread {thread_id}: {payload.message[:50]}...")

    response = chat_service.process_message(
        user_input=payload.message,
        thread_id=thread_id,
        tool_enabled=tool_enabled,
        provider=payload.provider,
        api_key=payload.api_key,
    )

    if response.get("error"):
        logger.error(f"Service error for thread {thread_id}: {response['error']}")
        raise HTTPException(status_code=500, detail=response["error"])

    return ChatResponse(
        final_answer=response["final_answer"],
        tool_calls=response["tool_calls"],
        thread_id=thread_id,
    )


@app.post("/chat/stream")
def chat_stream(payload: ChatRequest, x_api_key: Optional[str] = Header(None)):
    """
    Server-Sent Events stream of chat_service.process_message_stream events.

    This is a synchronous HTTP endpoint for now (one request = one stream).
    The Socket Service is expected to consume this and re-emit chunks to
    the browser over Socket.IO; it is not meant to be called from a browser
    directly.
    """
    require_api_key(x_api_key)

    thread_id = sanitize_thread_id(payload.thread_id)
    if not thread_id:
        raise HTTPException(status_code=400, detail="Invalid thread_id format")

    tool_enabled = payload.tool_enabled if payload.tool_enabled is not None else True

    logger.info(f"Streaming message for thread {thread_id}: {payload.message[:50]}...")

    def event_source():
        chunk_count = 0
        try:
            for event in chat_service.process_message_stream(
                user_input=payload.message,
                thread_id=thread_id,
                tool_enabled=tool_enabled,
                provider=payload.provider,
                api_key=payload.api_key,
            ):
                if event.get("type") == "chunk":
                    chunk_count += 1
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            logger.info(f"Finished streaming for thread {thread_id} ({chunk_count} chunks)")
        except Exception as e:
            logger.error(f"Error in chat_stream for thread {thread_id}: {e}", exc_info=True)
            error_event = {"type": "error", "error": "Internal server error"}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


# ─────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────

def main():
    import uvicorn

    logger.info("=" * 60)
    logger.info("SHOP CUSTOMER SERVICE CHATBOT - AI AGENT API SERVER")
    logger.info("=" * 60)
    logger.info(f"Host: {API_HOST}")
    logger.info(f"Port: {API_PORT}")
    logger.info(f"Langfuse: {'Enabled' if is_langfuse_enabled() else 'Disabled'}")
    logger.info(f"API Key Protection: {'Enabled' if API_KEY else 'Disabled (Dev Mode)'}")
    logger.info("=" * 60)

    if not API_KEY:
        logger.warning("WARNING: API_KEY not set - api_server endpoints are unprotected!")

    uvicorn.run(app, host=API_HOST, port=API_PORT)


if __name__ == "__main__":
    main()
