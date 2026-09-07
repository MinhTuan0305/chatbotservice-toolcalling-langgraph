"""
Socket Server for Shop Customer Service Chatbot

Real-time Socket.IO gateway that enables web/mobile clients to communicate
with the AI chatbot service. Holds no LangGraph/LLM logic itself — every
chat request is forwarded over HTTP to the AI Agent API server
(app/api_server.py, see app/ai_client.py) and the response/stream is
re-emitted to the relevant Socket.IO room.

Production features:
- Rate limiting to prevent abuse
- API key authentication for admin endpoints
- Enhanced logging with file output
- CORS security
- Request validation
- Error monitoring
"""

# Must run before any other import: patches socket/threading/time so that
# blocking calls (e.g. the `requests` calls in app/ai_client.py) cooperate
# with eventlet's event loop instead of blocking every connected client.
#
# EVENTLET_NO_GREENDNS disables eventlet's own pure-Python DNS resolver in
# favor of the OS resolver (via a thread). Eventlet's greendns has been
# unreliable resolving both "localhost" (hangs on Windows) and Docker
# Compose service names (hangs against Docker's embedded DNS) — both
# observed hanging/timing out in this project. Must be set before eventlet
# is imported.
import os
os.environ.setdefault("EVENTLET_NO_GREENDNS", "yes")
import eventlet
eventlet.monkey_patch()

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any
from functools import wraps
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, ConnectionRefusedError
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app import ai_client, auth
from app.config import (
    SOCKET_HOST, SOCKET_PORT, SOCKET_DEBUG, CORS_ORIGINS,
    RATE_LIMIT_ENABLED, RATE_LIMIT_DEFAULT, RATE_LIMIT_CHAT,
    API_KEY, JWT_EXPIRE_MINUTES, LOG_LEVEL, LOG_FILE, TRUST_PROXY_HEADERS
)
from app.observability.langfuse_client import is_langfuse_enabled

# ─────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────

# Create logs directory if not exists
os.makedirs('logs', exist_ok=True)

# Configure logging with both file and console handlers
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, origins=CORS_ORIGINS)

if TRUST_PROXY_HEADERS:
    # Behind exactly one reverse proxy hop (Nginx) — trust its
    # X-Forwarded-For/-Proto/-Host so request.remote_addr and url_for see
    # the real client, not the proxy.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[RATE_LIMIT_DEFAULT] if RATE_LIMIT_ENABLED else [],
    storage_uri="memory://"  # Use Redis in production: "redis://localhost:6379"
)

# Initialize Socket.IO with eventlet async mode
socketio = SocketIO(
    app,
    cors_allowed_origins=CORS_ORIGINS,
    async_mode='eventlet',
    logger=SOCKET_DEBUG,
    engineio_logger=SOCKET_DEBUG
)

# Thread state management (in-memory)
# Format: {thread_id: {tool_enabled: bool, connected_clients: int, last_activity: datetime}}
thread_states: Dict[str, Dict[str, Any]] = {}

# Authenticated clients (in-memory). Format: {socket_id: user_id}
# Populated on 'connect' after JWT verification, cleared on 'disconnect'.
authenticated_users: Dict[str, str] = {}


# ─────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────

def require_api_key(f):
    """Decorator to require API key for protected endpoints."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip if API_KEY not configured (development mode)
        if not API_KEY:
            logger.warning("API_KEY not configured - endpoint unprotected")
            return f(*args, **kwargs)
        
        # Check API key in header or query param
        provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        
        if not provided_key or provided_key != API_KEY:
            logger.warning(f"Unauthorized access attempt from {get_remote_address()} to {request.path}")
            return jsonify({'error': 'Unauthorized', 'message': 'Valid API key required'}), 401
        
        return f(*args, **kwargs)
    return decorated_function


def validate_input(data: dict, required_fields: list) -> tuple[bool, str]:
    """
    Validate that required fields are present and non-empty.
    
    Returns:
        (is_valid, error_message)
    """
    for field in required_fields:
        if field not in data:
            return False, f"{field} is required"
        
        value = data[field]
        
        # Check if string field is empty
        if isinstance(value, str) and not value.strip():
            return False, f"{field} cannot be empty"
    
    return True, ""


def sanitize_thread_id(thread_id: str) -> str:
    """
    Sanitize thread ID to prevent injection attacks.

    Allows: alphanumeric, dash, underscore
    Max length: 100 chars
    """
    # Remove invalid characters
    sanitized = re.sub(r'[^a-zA-Z0-9\-_]', '', thread_id)

    # Limit length
    sanitized = sanitized[:100]

    return sanitized


def authorize_thread(client_id: str, thread_id: str) -> bool:
    """
    Each authenticated user owns exactly one conversation thread: their own
    user_id. Prevents an authenticated client from reading/writing another
    user's thread by guessing/typing its thread_id.
    """
    user_id = authenticated_users.get(client_id)
    return user_id is not None and thread_id == user_id


def get_thread_state(thread_id: str) -> Dict[str, Any]:
    """Get or create thread state."""
    if thread_id not in thread_states:
        thread_states[thread_id] = {
            'tool_enabled': True,
            'connected_clients': 0,
            'last_activity': datetime.now()
        }
    return thread_states[thread_id]


def update_thread_activity(thread_id: str):
    """Update last activity timestamp for thread."""
    if thread_id in thread_states:
        thread_states[thread_id]['last_activity'] = datetime.now()


def cleanup_old_threads():
    """Remove threads inactive for more than 24 hours."""
    now = datetime.now()
    inactive_threads = [
        tid for tid, state in thread_states.items()
        if now - state['last_activity'] > timedelta(hours=24)
    ]
    for tid in inactive_threads:
        del thread_states[tid]
        logger.info(f"Cleaned up inactive thread: {tid}")


# ─────────────────────────────────────────────
# Socket Event Handlers
# ─────────────────────────────────────────────

@socketio.on('connect')
def handle_connect(auth_payload):
    """
    Handle client connection.

    Requires a JWT in the Socket.IO connection handshake:
        io("http://host:5000", { auth: { token: "<jwt>" } })

    Get a token via POST /auth/token first. Connection is refused if the
    token is missing, malformed, or expired.
    """
    client_id = request.sid
    token = (auth_payload or {}).get('token') if isinstance(auth_payload, dict) else None

    try:
        user_id = auth.verify_token(token)
    except auth.TokenError as e:
        logger.warning(f"Rejected connection from {client_id}: {e}")
        raise ConnectionRefusedError(str(e))

    authenticated_users[client_id] = user_id
    logger.info(f"Client connected: {client_id} (user_id={user_id})")

    emit('connected', {
        'status': 'ok',
        'message': 'Connected to Shop Chatbot Server',
        'user_id': user_id,
        'langfuse_enabled': is_langfuse_enabled()
    })


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    client_id = request.sid
    logger.info(f"Client disconnected: {client_id}")

    authenticated_users.pop(client_id, None)

    # Cleanup: decrease connected clients count
    # Note: We don't know which thread this client was in,
    # but it's okay - counts are approximate


@socketio.on('join_thread')
def handle_join_thread(data):
    """
    Handle client joining a conversation thread.
    
    Expected data:
        {
            "thread_id": "shop-001"
        }
    """
    try:
        # Validate input
        is_valid, error_msg = validate_input(data, ['thread_id'])
        if not is_valid:
            emit('error', {'error': error_msg})
            return
        
        thread_id = sanitize_thread_id(data['thread_id'])

        if not thread_id:
            emit('error', {'error': 'Invalid thread_id format'})
            return

        if not authorize_thread(request.sid, thread_id):
            emit('error', {'error': 'You can only join your own thread (thread_id must match your authenticated user_id)'})
            return

        # Join Socket.IO room
        join_room(thread_id)
        
        # Update thread state
        state = get_thread_state(thread_id)
        state['connected_clients'] += 1
        update_thread_activity(thread_id)
        
        logger.info(f"Client {request.sid} joined thread: {thread_id}")
        
        emit('thread_joined', {
            'status': 'joined',
            'thread_id': thread_id,
            'tool_enabled': state['tool_enabled']
        })
        
    except Exception as e:
        logger.error(f"Error in join_thread: {e}", exc_info=True)
        emit('error', {'error': str(e)})


@socketio.on('leave_thread')
def handle_leave_thread(data):
    """
    Handle client leaving a conversation thread.
    
    Expected data:
        {
            "thread_id": "shop-001"
        }
    """
    try:
        # Validate input
        is_valid, error_msg = validate_input(data, ['thread_id'])
        if not is_valid:
            emit('error', {'error': error_msg})
            return
        
        thread_id = sanitize_thread_id(data['thread_id'])

        if not authorize_thread(request.sid, thread_id):
            emit('error', {'error': 'You can only leave your own thread'})
            return

        # Leave Socket.IO room
        leave_room(thread_id)
        
        # Update thread state
        if thread_id in thread_states:
            thread_states[thread_id]['connected_clients'] = max(
                0, thread_states[thread_id]['connected_clients'] - 1
            )
        
        logger.info(f"Client {request.sid} left thread: {thread_id}")
        
        emit('thread_left', {
            'status': 'left',
            'thread_id': thread_id
        })
        
    except Exception as e:
        logger.error(f"Error in leave_thread: {e}", exc_info=True)
        emit('error', {'error': str(e)})


@socketio.on('chat_message')
def handle_chat_message(data):
    """
    Handle non-streaming chat message.
    
    Expected data:
        {
            "message": "Top 5 khách hàng",
            "thread_id": "shop-001",
            "tool_enabled": true (optional)
        }
    
    Rate limited to RATE_LIMIT_CHAT per client.
    """
    try:
        # Validate input
        is_valid, error_msg = validate_input(data, ['message', 'thread_id'])
        if not is_valid:
            emit('error', {'error': error_msg})
            return
        
        message = data['message']
        thread_id = sanitize_thread_id(data['thread_id'])
        tool_enabled = data.get('tool_enabled')

        if not authorize_thread(request.sid, thread_id):
            emit('error', {'error': 'You can only send messages to your own thread'})
            return

        # Validate message length (max 5000 chars)
        if len(message) > 5000:
            emit('error', {'error': 'Message too long (max 5000 characters)'})
            return

        # Get tool_enabled from thread state if not provided
        if tool_enabled is None:
            state = get_thread_state(thread_id)
            tool_enabled = state['tool_enabled']
        
        update_thread_activity(thread_id)

        logger.info(f"Processing message for thread {thread_id} from {request.sid}: {message[:50]}...")

        # Forward to the AI Agent API server
        try:
            response = ai_client.chat(
                message=message,
                thread_id=thread_id,
                tool_enabled=tool_enabled
            )
        except ai_client.AIServiceError as e:
            logger.error(f"AI service error for thread {thread_id}: {e}")
            emit('error', {
                'error': str(e),
                'thread_id': thread_id
            }, room=thread_id)
            return

        # Send response to room
        emit('bot_response', {
            'final_answer': response['final_answer'],
            'tool_calls': response['tool_calls'],
            'thread_id': thread_id
        }, room=thread_id)
        
        logger.info(f"Sent response for thread {thread_id}")
        
    except Exception as e:
        logger.error(f"Error in chat_message: {e}", exc_info=True)
        emit('error', {
            'error': 'Internal server error',
            'thread_id': data.get('thread_id')
        })


@socketio.on('chat_stream')
def handle_chat_stream(data):
    """
    Handle streaming chat message.
    
    Expected data:
        {
            "message": "Top 5 khách hàng",
            "thread_id": "shop-001",
            "tool_enabled": true (optional)
        }
    
    Rate limited to RATE_LIMIT_CHAT per client.
    """
    try:
        # Validate input
        is_valid, error_msg = validate_input(data, ['message', 'thread_id'])
        if not is_valid:
            emit('error', {'error': error_msg}, room=data.get('thread_id'))
            return
        
        message = data['message']
        thread_id = sanitize_thread_id(data['thread_id'])
        tool_enabled = data.get('tool_enabled')

        if not authorize_thread(request.sid, thread_id):
            emit('error', {'error': 'You can only stream to your own thread'})
            return

        # Validate message length
        if len(message) > 5000:
            emit('error', {'error': 'Message too long (max 5000 characters)'}, room=thread_id)
            return

        # Get tool_enabled from thread state if not provided
        if tool_enabled is None:
            state = get_thread_state(thread_id)
            tool_enabled = state['tool_enabled']
        
        update_thread_activity(thread_id)

        logger.info(f"Streaming message for thread {thread_id} from {request.sid}: {message[:50]}...")

        # Stream from the AI Agent API server (single SSE connection, re-emitted chunk by chunk)
        chunk_count = 0
        for event in ai_client.chat_stream(
            message=message,
            thread_id=thread_id,
            tool_enabled=tool_enabled
        ):
            # Emit each event to the room
            emit('bot_chunk', event, room=thread_id)
            
            if event['type'] == 'chunk':
                chunk_count += 1
            
            # Small delay to prevent flooding
            socketio.sleep(0.01)
        
        logger.info(f"Finished streaming for thread {thread_id} ({chunk_count} chunks)")
        
    except Exception as e:
        logger.error(f"Error in chat_stream: {e}", exc_info=True)
        emit('error', {
            'error': 'Internal server error',
            'thread_id': data.get('thread_id')
        }, room=data.get('thread_id'))


@socketio.on('toggle_tools')
def handle_toggle_tools(data):
    """
    Toggle tools on/off for a thread.
    
    Expected data:
        {
            "thread_id": "shop-001",
            "enabled": false
        }
    """
    try:
        # Validate input
        is_valid, error_msg = validate_input(data, ['thread_id'])
        if not is_valid:
            emit('error', {'error': error_msg})
            return
        
        thread_id = sanitize_thread_id(data['thread_id'])
        enabled = data.get('enabled')

        if enabled is None:
            emit('error', {'error': 'enabled is required'})
            return

        if not authorize_thread(request.sid, thread_id):
            emit('error', {'error': 'You can only toggle tools on your own thread'})
            return

        # Update thread state
        state = get_thread_state(thread_id)
        state['tool_enabled'] = bool(enabled)
        update_thread_activity(thread_id)
        
        logger.info(f"Tools {'enabled' if enabled else 'disabled'} for thread {thread_id} by {request.sid}")
        
        emit('tools_toggled', {
            'status': 'ok',
            'thread_id': thread_id,
            'tool_enabled': state['tool_enabled']
        }, room=thread_id)
        
    except Exception as e:
        logger.error(f"Error in toggle_tools: {e}", exc_info=True)
        emit('error', {'error': str(e)})


# ─────────────────────────────────────────────
# HTTP Routes
# ─────────────────────────────────────────────

@app.route('/auth/token', methods=['POST'])
@limiter.limit("10 per minute")
def issue_token():
    """
    DEMO token issuer.

    Exchanges a client-supplied user_id for a signed JWT — there is no
    password/credential check here, this only exists so the Socket.IO
    'connect' handshake has a token to verify. A real deployment would
    replace this with actual authentication against a user store.

    Request body: {"user_id": "some-user"}
    Response: {"token": "...", "user_id": "some-user", "expires_in_minutes": 60}
    """
    data = request.get_json(silent=True) or {}
    user_id = (data.get('user_id') or '').strip()

    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    if not re.fullmatch(r'[a-zA-Z0-9\-_]{1,100}', user_id):
        return jsonify({
            'error': 'user_id must be 1-100 chars: letters, digits, dash, underscore only'
        }), 400

    token = auth.create_token(user_id)

    return jsonify({
        'token': token,
        'user_id': user_id,
        'expires_in_minutes': JWT_EXPIRE_MINUTES
    })


@app.route('/health')
@limiter.limit("30 per minute")
@require_api_key
def health_check():
    """
    Health check endpoint for load balancers and monitoring.
    
    Requires API key in production.
    """
    return jsonify({
        'status': 'ok',
        'service': 'shop-chatbot-socket',
        'version': '1.0.0',
        'langfuse_enabled': is_langfuse_enabled(),
        'rate_limiting': RATE_LIMIT_ENABLED
    })


@app.route('/stats')
@limiter.limit("10 per minute")
@require_api_key
def stats():
    """
    Server statistics endpoint for monitoring.
    
    Requires API key in production.
    Returns detailed stats about active threads and clients.
    """
    # Cleanup old threads before reporting
    cleanup_old_threads()
    
    return jsonify({
        'active_threads': len(thread_states),
        'total_clients': sum(
            state['connected_clients'] 
            for state in thread_states.values()
        ),
        'rate_limiting': {
            'enabled': RATE_LIMIT_ENABLED,
            'default': RATE_LIMIT_DEFAULT,
            'chat': RATE_LIMIT_CHAT
        },
        'threads': {
            tid: {
                'connected_clients': state['connected_clients'],
                'tool_enabled': state['tool_enabled'],
                'last_activity': state['last_activity'].isoformat()
            }
            for tid, state in thread_states.items()
        }
    })


@app.route('/metrics')
@limiter.limit("60 per minute")
@require_api_key
def metrics():
    """
    Prometheus-style metrics endpoint.
    
    Requires API key in production.
    """
    cleanup_old_threads()
    
    metrics_output = []
    metrics_output.append(f"# HELP socket_active_threads Number of active conversation threads")
    metrics_output.append(f"# TYPE socket_active_threads gauge")
    metrics_output.append(f"socket_active_threads {len(thread_states)}")
    
    metrics_output.append(f"# HELP socket_total_clients Total number of connected clients")
    metrics_output.append(f"# TYPE socket_total_clients gauge")
    total_clients = sum(state['connected_clients'] for state in thread_states.values())
    metrics_output.append(f"socket_total_clients {total_clients}")
    
    metrics_output.append(f"# HELP socket_langfuse_enabled Whether Langfuse observability is enabled")
    metrics_output.append(f"# TYPE socket_langfuse_enabled gauge")
    metrics_output.append(f"socket_langfuse_enabled {1 if is_langfuse_enabled() else 0}")
    
    return '\n'.join(metrics_output), 200, {'Content-Type': 'text/plain; charset=utf-8'}


# ─────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────

def main():
    """Start the socket server."""
    logger.info("=" * 60)
    logger.info("SHOP CUSTOMER SERVICE CHATBOT - SOCKET SERVER")
    logger.info("=" * 60)
    logger.info(f"Host: {SOCKET_HOST}")
    logger.info(f"Port: {SOCKET_PORT}")
    logger.info(f"Debug: {SOCKET_DEBUG}")
    logger.info(f"CORS: {CORS_ORIGINS}")
    logger.info(f"Langfuse: {'Enabled' if is_langfuse_enabled() else 'Disabled'}")
    logger.info(f"Rate Limiting: {'Enabled' if RATE_LIMIT_ENABLED else 'Disabled'}")
    if RATE_LIMIT_ENABLED:
        logger.info(f"  - Default: {RATE_LIMIT_DEFAULT}")
        logger.info(f"  - Chat: {RATE_LIMIT_CHAT}")
    logger.info(f"API Key Protection: {'Enabled' if API_KEY else 'Disabled (Dev Mode)'}")
    logger.info(f"Trust Proxy Headers: {TRUST_PROXY_HEADERS}")
    logger.info(f"Log Level: {LOG_LEVEL}")
    logger.info(f"Log File: {LOG_FILE}")
    logger.info("=" * 60)
    
    if not API_KEY:
        logger.warning("⚠️  WARNING: API_KEY not set - /health and /stats endpoints are unprotected!")
        logger.warning("⚠️  Set API_KEY in .env for production deployment")
    
    if CORS_ORIGINS == "*":
        logger.warning("⚠️  WARNING: CORS is wide open (*) - restrict in production!")
    
    # Run server with eventlet
    socketio.run(
        app,
        host=SOCKET_HOST,
        port=SOCKET_PORT,
        debug=SOCKET_DEBUG,
        use_reloader=False  # Disable reloader in production
    )


if __name__ == '__main__':
    main()
