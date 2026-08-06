from redis import Redis

from langgraph.checkpoint.redis import RedisSaver

from app.config import REDIS_URL

def create_checkpointer() -> RedisSaver:
    client = Redis.from_url(
        REDIS_URL,
        decode_responses=False,
    )

    checkpointer = RedisSaver(
        redis_client=client
    )

    checkpointer.setup()

    return checkpointer

