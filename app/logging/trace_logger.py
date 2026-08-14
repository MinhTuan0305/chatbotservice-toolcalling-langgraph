import json
import uuid

from datetime import datetime
from pathlib import Path


TRANSCRIPT_FILE = Path(
    "logs/transcripts.json"
)


def get_timestamp() -> str:
    return datetime.now().isoformat()


def load_transcripts() -> list[dict]:
    """
    Đọc toàn bộ transcript hiện có.
    """

    if not TRANSCRIPT_FILE.exists():
        return []

    with open(
        TRANSCRIPT_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def save_transcripts(
    transcripts: list[dict],
):
    """
    Ghi toàn bộ transcript
    vào file JSON.
    """

    TRANSCRIPT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(
        TRANSCRIPT_FILE,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            transcripts,
            file,
            ensure_ascii=False,
            indent=2,
            default=str,
        )


def save_transcript(
    user_input: str,
    tool_calls: list[dict],
    final_answer: str,
    execution_metrics: dict | None = None,
):
    """
    Lưu một lần user hỏi chatbot.

    Mỗi lần gọi hàm này sẽ append
    một transcript mới vào JSON.
    """

    transcripts = load_transcripts()

    transcript = {

        "id": str(
            uuid.uuid4()
        ),

        "timestamp": get_timestamp(),

        "user": {
            "input": user_input,
        },

        "tool_calls": tool_calls,

        "assistant": {
            "final_answer": final_answer,
        },
        
        "execution_metrics": execution_metrics or {},  # Add metrics
    }

    transcripts.append(
        transcript
    )

    save_transcripts(
        transcripts
    )