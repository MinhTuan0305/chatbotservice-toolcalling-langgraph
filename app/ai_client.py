"""
HTTP client for the AI Agent API Server (app/api_server.py).

socket_server.py is a real-time gateway only: it holds no LangGraph/LLM
logic itself and forwards every chat request to the AI service over HTTP.
Non-streaming calls hit POST /chat once; streaming calls hold a single SSE
connection open to POST /chat/stream and re-emit each event as it arrives
(no per-chunk HTTP round-trip).
"""

import json
import logging
from typing import Any, Dict, Generator, Optional

import requests

from app.config import AI_SERVICE_URL, API_KEY

logger = logging.getLogger(__name__)

_session = requests.Session()

_CONNECT_TIMEOUT = 10   # time to establish connection / receive first byte
_READ_TIMEOUT = 60      # non-streaming: time to receive the full response
_STREAM_READ_TIMEOUT = 120  # streaming: max gap between chunks


class AIServiceError(Exception):
    """Raised when the AI service is unreachable or returns an error."""


def _headers() -> Dict[str, str]:
    # Connection: close disables HTTP keep-alive reuse on this session's pool.
    # Without it, a connection left over from before api_server last
    # restarted/redeployed can sit in the pool looking alive; reusing it
    # then stalls for tens of seconds (an OS-level TCP timeout) before
    # urllib3 notices it's dead and retries. A fresh connection per call
    # costs a few ms on the internal docker network — cheap next to LLM
    # latency, and it removes this failure mode entirely.
    headers = {"Connection": "close"}
    if API_KEY:
        headers["x-api-key"] = API_KEY
    return headers


def _extract_detail(resp: requests.Response) -> str:
    try:
        data = resp.json()
        detail = data.get("detail", resp.text)
        return detail if isinstance(detail, str) else json.dumps(detail)
    except ValueError:
        return resp.text or f"HTTP {resp.status_code}"


def chat(
    message: str,
    thread_id: str,
    tool_enabled: bool,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Call POST /chat (non-streaming). Returns the parsed JSON response."""
    payload = {"message": message, "thread_id": thread_id, "tool_enabled": tool_enabled}
    if provider:
        payload["provider"] = provider
    if api_key:
        payload["api_key"] = api_key
    try:
        resp = _session.post(
            f"{AI_SERVICE_URL}/chat",
            json=payload,
            headers=_headers(),
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
        )
    except requests.RequestException as e:
        logger.error(f"AI service unreachable: {e}")
        raise AIServiceError("AI service unreachable") from e

    if resp.status_code != 200:
        raise AIServiceError(_extract_detail(resp))

    return resp.json()


def chat_stream(
    message: str,
    thread_id: str,
    tool_enabled: bool,
    provider: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Call POST /chat/stream (SSE) and yield each decoded event as it arrives."""
    payload = {"message": message, "thread_id": thread_id, "tool_enabled": tool_enabled}
    if provider:
        payload["provider"] = provider
    if api_key:
        payload["api_key"] = api_key
    try:
        resp = _session.post(
            f"{AI_SERVICE_URL}/chat/stream",
            json=payload,
            headers=_headers(),
            timeout=(_CONNECT_TIMEOUT, _STREAM_READ_TIMEOUT),
            stream=True,
        )
    except requests.RequestException as e:
        logger.error(f"AI service unreachable: {e}")
        yield {"type": "error", "error": "AI service unreachable"}
        return

    if resp.status_code != 200:
        yield {"type": "error", "error": _extract_detail(resp)}
        resp.close()
        return

    try:
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            try:
                yield json.loads(line[len("data: "):])
            except json.JSONDecodeError:
                logger.error(f"Malformed SSE line from AI service: {line[:200]}")
    except requests.RequestException as e:
        logger.error(f"AI service stream interrupted: {e}")
        yield {"type": "error", "error": "AI service stream interrupted"}
    finally:
        resp.close()
