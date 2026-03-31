"""Orchestrator — reads Redis stream, runs all 3 LLM modules per job.

Concurrency: Semaphore(1) so only one job runs at a time (free-tier safe).
Each job fires 3 concurrent module calls via asyncio.gather().
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import httpx

from src.db import save_validation
from src.modules.competitors import find_competitors
from src.modules.market import analyse_market
from src.modules.viability import score_viability
from src.redis_client import get_redis, publish_result

logger = logging.getLogger(__name__)

# Free-tier concurrency cap: 1 job at a time (3 RPM per job, within 5 RPM limit)
_semaphore = asyncio.Semaphore(1)


async def _process_job(job_id: str, idea: str, msg_id: str) -> None:
    """Process a single validation job: run 3 modules, persist, publish."""
    async with _semaphore:
        logger.info("[orchestrator] job %s running", job_id)

        # Update status → running in DB
        await save_validation({"job_id": job_id, "idea": idea, "status": "running"})

        # Single httpx client for this job — shared by all 3 modules
        async with httpx.AsyncClient() as client:
            results = await asyncio.gather(
                analyse_market(idea, client),
                find_competitors(idea, client),
                score_viability(idea, client),
                return_exceptions=True,
            )

        # Unpack — treat any Exception as {"error": True}
        market = results[0] if not isinstance(results[0], Exception) else {"error": True}
        competitors = results[1] if not isinstance(results[1], Exception) else {"error": True}
        viability = results[2] if not isinstance(results[2], Exception) else {"error": True}

        # Determine overall status
        has_error = any(
            isinstance(r, dict) and r.get("error") for r in [market, competitors, viability]
        )
        status = "error" if all(
            isinstance(r, dict) and r.get("error") for r in [market, competitors, viability]
        ) else "done"

        # Persist full result to PostgreSQL
        await save_validation({
            "job_id": job_id,
            "idea": idea,
            "status": status,
            "market": market,
            "competitors": competitors,
            "viability": viability,
        })

        # Publish to per-job Redis result stream
        await publish_result(job_id, {
            "job_id": job_id,
            "status": status,
            "market": market,
            "competitors": competitors,
            "viability": viability,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })

        logger.info("[orchestrator] job %s %s", job_id, status)
        
        # ACK the message in the consumer group
        r = await get_redis()
        await r.xack("validator:jobs", "orchestrator", msg_id)


async def run_orchestrator() -> None:
    """Infinite loop: read jobs from Redis stream via consumer group, process each."""
    from src.redis_client import ensure_consumer_group

    await ensure_consumer_group()
    logger.info("[orchestrator] consumer started — waiting for jobs…")

    r = await get_redis()
    consumer_name = "worker-1"

    while True:
        try:
            # Block-read from consumer group (5 s timeout, then re-loop)
            messages = await r.xreadgroup(
                groupname="orchestrator",
                consumername=consumer_name,
                streams={"validator:jobs": ">"},
                count=1,
                block=5000,
            )

            if not messages:
                continue

            for stream_name, entries in messages:
                for msg_id, fields in entries:
                    job_id = fields.get("job_id", "")
                    idea = fields.get("idea", "")

                    if not job_id or not idea:
                        logger.warning("Malformed job entry %s — skipping", msg_id)
                        await r.xack("validator:jobs", "orchestrator", msg_id)
                        continue

                    # Process job as a task (semaphore limits concurrency)
                    # We do not await it here so the loop can keep reading, but 
                    # semaphore will prevent multiple from running concurrently
                    asyncio.create_task(_process_job(job_id, idea, msg_id))

        except Exception as exc:
            logger.error("[orchestrator] stream read error: %s — retrying in 5s", exc)
            await asyncio.sleep(5)
