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


if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY chưa được cấu hình trong .env"
    )


if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL chưa được cấu hình trong .env"
    )