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

# Rate limiting
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() == "true"
RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "100 per minute")
RATE_LIMIT_CHAT = os.getenv("RATE_LIMIT_CHAT", "20 per minute")

# API security
API_KEY = os.getenv("API_KEY")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/socket_server.log")



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