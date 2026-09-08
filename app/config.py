import os

from dotenv import load_dotenv


load_dotenv()


GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
)

# OpenAI is an opt-in provider switched to at runtime (see app/graph/nodes.py)
# with a client-supplied API key — there is no OPENAI_API_KEY default here on
# purpose, only the model name to use once a key is provided.
OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini",
)

DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

REDIS_URL = os.getenv(
    "REDIS_URL"
)

# Langfuse Observability (optional)
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")

# Message trimming configuration
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "4000"))

# Socket server configuration
SOCKET_HOST = os.getenv("SOCKET_HOST", "0.0.0.0")
SOCKET_PORT = int(os.getenv("SOCKET_PORT", "5000"))
SOCKET_DEBUG = os.getenv("SOCKET_DEBUG", "False").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# AI Agent API server configuration (FastAPI, standalone service)
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_LOG_FILE = os.getenv("API_LOG_FILE", "logs/api_server.log")

# Reachable base URL of the AI Agent API server, used by socket_server.py
# (the gateway) to call it over HTTP. Distinct from API_HOST/API_PORT above,
# which are bind addresses (0.0.0.0 is not a valid client target).
# Use 127.0.0.1, not "localhost": eventlet's monkey-patched DNS resolver
# (required by socket_server.py) can hang resolving "localhost" on Windows.
AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", f"http://127.0.0.1:{API_PORT}")

# Rate limiting
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "100 per minute")
RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "20 per minute")

# API security
API_KEY = os.getenv("API_KEY")

# JWT authentication for end-user clients connecting to the Socket gateway
# (distinct from API_KEY above, which is a static service-to-service secret)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/socket_server.log")

# Set True only when socket_server sits behind exactly one trusted reverse
# proxy hop (e.g. the Nginx service in docker-compose.yml), so it knows to
# trust one X-Forwarded-For/X-Forwarded-Proto hop for rate limiting and
# logging. Leave False for direct/local runs — otherwise a client could
# spoof its own X-Forwarded-For header to dodge per-IP rate limits.
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "False").lower() == "true"



if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY chưa được cấu hình trong .env"
    )


if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL chưa được cấu hình trong .env"
    )


if not REDIS_URL:
    raise ValueError(
        "REDIS_URL chưa được cấu hình trong .env"
    )


if not JWT_SECRET_KEY:
    raise ValueError(
        "JWT_SECRET_KEY chưa được cấu hình trong .env"
    )