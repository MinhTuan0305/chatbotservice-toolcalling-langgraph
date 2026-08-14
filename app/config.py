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