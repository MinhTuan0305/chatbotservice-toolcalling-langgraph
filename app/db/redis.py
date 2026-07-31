from redis import Redis

from langgraph.checkpoint.redis import RedisSaver

client = Redis(
    host="localhost",
    port=6379,
    decode_responses=False,
)

checkpointer = RedisSaver(
    redis_client=client
)

checkpointer.setup()