"""Redis connection and stream helpers."""

import json
import logging
from datetime import datetime

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from src.config import settings

logger = logging.getLogger(__name__)

# Lazy-initialised connection (set in main.py lifespan)
redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return the async Redis connection, creating it if needed."""
    global redis
    if redis is None:
        redis = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
    return redis


async def close_redis() -> None:
    """Cleanly close the Redis connection."""
    global redis
    if redis is not None:
        await redis.close()
        redis = None


# ── Stream helpers ───────────────────────────────────────


async def enqueue_job(job_id: str, idea: str) -> None:
    """Add a validation job to the validator:jobs stream (flat string fields)."""
    r = await get_redis()
    await r.xadd(
        "validator:jobs",
        {
            "job_id": job_id,
            "idea": idea,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
        },
    )
    logger.info("Enqueued job %s", job_id)


async def publish_result(job_id: str, result_dict: dict) -> None:
    """Write completed results to the per-job result stream.

    All nested fields are JSON-serialised to strings (Redis streams
    only accept flat string key-value pairs).
    """
    r = await get_redis()
    flat: dict[str, str] = {}
    for key, value in result_dict.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value)
        else:
            flat[key] = str(value)

    stream_key = f"validator:result:{job_id}"
    await r.xadd(stream_key, flat)
    await r.expire(stream_key, 3600)  # TTL 1 hour
    logger.info("Published result for job %s", job_id)


async def ensure_consumer_group() -> None:
    """Create the orchestrator consumer group on validator:jobs.

    Safe to call multiple times — swallows BUSYGROUP error.
    """
    r = await get_redis()
    try:
        await r.xgroup_create(
            "validator:jobs", "orchestrator", id="0", mkstream=True
        )
        logger.info("Created consumer group 'orchestrator'")
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            pass  # group already exists — safe to ignore
        else:
            raise
