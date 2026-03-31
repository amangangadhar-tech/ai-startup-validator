"""PostgreSQL connection, session factory, and helpers."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config import settings
from src.models import Base, Validation

logger = logging.getLogger(__name__)

# Async engine + session factory (created at import time, connected lazily)
engine = create_async_engine(settings.database_url, echo=False, pool_size=5)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables on startup (idempotent)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialised")


async def save_validation(job: dict) -> None:
    """Upsert a validation row by job_id.

    If the row already exists (status='queued'), update it with results.
    Otherwise, insert a new row.
    """
    async with async_session() as session:
        async with session.begin():
            existing = await session.execute(
                select(Validation).where(Validation.id == job["job_id"])
            )
            row = existing.scalar_one_or_none()

            if row:
                # Update existing row with results
                row.status = job.get("status", row.status)
                row.market = job.get("market")
                row.competitors = job.get("competitors")
                row.viability = job.get("viability")
                if job.get("status") == "done":
                    row.completed_at = datetime.now(timezone.utc)
            else:
                # Insert new row
                row = Validation(
                    id=job["job_id"],
                    idea=job["idea"],
                    status=job.get("status", "queued"),
                    market=job.get("market"),
                    competitors=job.get("competitors"),
                    viability=job.get("viability"),
                )
                session.add(row)

    logger.info("Saved validation %s (status=%s)", job["job_id"], job.get("status"))


async def get_history(limit: int = 20) -> list[dict]:
    """Return the last N validations ordered by created_at DESC."""
    async with async_session() as session:
        result = await session.execute(
            select(Validation)
            .order_by(Validation.created_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        return [
            {
                "id": str(row.id),
                "idea": row.idea,
                "status": row.status,
                "market": row.market,
                "competitors": row.competitors,
                "viability": row.viability,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            }
            for row in rows
        ]


async def get_validation(job_id: str) -> dict | None:
    """Fetch a single validation by ID."""
    async with async_session() as session:
        result = await session.execute(
            select(Validation).where(Validation.id == job_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return {
            "id": str(row.id),
            "idea": row.idea,
            "status": row.status,
            "market": row.market,
            "competitors": row.competitors,
            "viability": row.viability,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
