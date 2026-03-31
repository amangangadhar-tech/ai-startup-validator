"""FastAPI app entry point — routes only, no business logic yet."""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse

from src.config import settings
from src.db import get_history, get_validation, init_db, save_validation
from src.models import HealthResponse, IdeaRequest, JobResponse
from src.orchestrator import run_orchestrator
from src.redis_client import ensure_consumer_group, enqueue_job, get_redis

# ── Logging ──────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    # Startup
    logger.info("Initialising database tables…")
    await init_db()

    logger.info("Ensuring Redis consumer group…")
    await ensure_consumer_group()
    
    logger.info("Starting orchestrator background task…")
    app.state.orchestrator_task = asyncio.create_task(run_orchestrator())

    logger.info("✅ Startup complete")
    yield

    # Shutdown
    if getattr(app.state, "orchestrator_task", None):
        app.state.orchestrator_task.cancel()
        
    from src.redis_client import close_redis
    await close_redis()
    logger.info("🛑 Shutdown complete")


# ── App ──────────────────────────────────────────────────

app = FastAPI(
    title="Startup Idea Validator",
    description="Validate startup ideas with AI-powered market, competitor, and viability analysis.",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Routes ───────────────────────────────────────────────

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve the single-file dashboard."""
    html_path = STATIC_DIR / "dashboard.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(html_path, media_type="text/html")


@app.post("/validate", response_model=JobResponse)
async def validate_idea(body: IdeaRequest):
    """Accept a startup idea, enqueue it for validation, return job_id."""
    idea = body.idea.strip()
    if not idea:
        raise HTTPException(status_code=422, detail="Idea cannot be empty")

    job_id = str(uuid.uuid4())

    # Persist initial row in PostgreSQL (status=queued)
    await save_validation({"job_id": job_id, "idea": idea, "status": "queued"})

    # Enqueue to Redis stream
    await enqueue_job(job_id, idea)

    logger.info("Job %s queued for idea: %.80s…", job_id, idea)
    return JobResponse(job_id=job_id)


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    """Fetch full validation results from PostgreSQL."""
    result = await get_validation(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=result)


@app.get("/stream/{job_id}")
async def stream_results(job_id: str):
    """SSE endpoint tracking per-job result stream on Redis."""
    async def event_generator():
        r = await get_redis()
        stream_key = f"validator:result:{job_id}"
        last_id = "0"
        
        while True:
            # Block for up to 30s waiting for a message
            messages = await r.xread({stream_key: last_id}, count=1, block=30000)
            if not messages:
                continue  # Keep waiting if timeout
                
            for stream_name, entries in messages:
                for msg_id, fields in entries:
                    last_id = msg_id
                    
                    # Unpack fields into standard dict
                    payload = {"job_id": fields.get("job_id"), "status": fields.get("status")}
                    
                    # Deserialize JSON strings back into objects
                    for key in ["market", "competitors", "viability"]:
                        if key in fields:
                            try:
                                payload[key] = json.loads(fields[key])
                            except json.JSONDecodeError:
                                pass
                                
                    if "completed_at" in fields:
                        payload["completed_at"] = fields["completed_at"]

                    # Yield the event
                    yield {
                        "event": "message",
                        "data": json.dumps(payload),
                    }
                    
                    # Close connection when job transitions to terminal state
                    if payload.get("status") in ("done", "error"):
                        return
                        
    return EventSourceResponse(event_generator())


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Simple health check."""
    return HealthResponse(status="ok")


@app.get("/history")
async def history():
    """Return the last 20 validations from PostgreSQL."""
    rows = await get_history(limit=20)
    return JSONResponse(content=rows)
