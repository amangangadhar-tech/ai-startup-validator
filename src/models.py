"""Pydantic request/response models and SQLAlchemy ORM model."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase


# ── SQLAlchemy Base ──────────────────────────────────────


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


class Validation(Base):
    """PostgreSQL 'validations' table — matches SKILL.md schema exactly.

    CREATE TABLE validations (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        idea         TEXT NOT NULL,
        status       VARCHAR(10) NOT NULL DEFAULT 'queued',
        market       JSONB,
        competitors  JSONB,
        viability    JSONB,
        created_at   TIMESTAMPTZ DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    );
    """
    __tablename__ = "validations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idea = Column(Text, nullable=False)
    status = Column(String(10), nullable=False, default="queued")
    market = Column(JSONB, nullable=True)
    competitors = Column(JSONB, nullable=True)
    viability = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_validations_created_at_desc", created_at.desc()),
    )


# ── Pydantic Models ─────────────────────────────────────


class IdeaRequest(BaseModel):
    """POST /validate request body."""
    idea: str = Field(..., min_length=1, description="The startup idea to validate")


class JobResponse(BaseModel):
    """POST /validate response."""
    job_id: str


class ValidationResult(BaseModel):
    """GET /results/{job_id} response."""
    id: str
    idea: str
    status: str
    market: Optional[dict] = None
    competitors: Optional[dict] = None
    viability: Optional[dict] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class HealthResponse(BaseModel):
    """GET /health response."""
    status: str = "ok"
