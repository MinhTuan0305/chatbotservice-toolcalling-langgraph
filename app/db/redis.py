from redis import Redis

from langgraph.checkpoint.redis import RedisSaver

import logging

from app.config import (
    REDIS_HOST,
    REDIS_PORT,
    REDIS_DB,
    REDIS_PASSWORD
)

client = Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=False,
)

checkpointer = RedisSaver(
    redis_client=client
)

logger =logging.getLogger(__name__)

try:
    checkpointer.setup()
except Exception:
    logger.exception("Redis setup failed")
    raise