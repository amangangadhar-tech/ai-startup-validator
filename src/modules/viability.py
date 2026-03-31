"""Module 3 — Viability Scorer.

Calls NVIDIA NIM to produce a structured viability assessment
with overall score, verdict, dimensional breakdown, risks, and next steps.
Returns a parsed dict.
"""

import asyncio
import json
import logging
import re

import httpx

from src.nvidia import nvidia_chat

logger = logging.getLogger(__name__)

SYSTEM = """You are a startup viability analyst at a top-tier VC. Given a startup idea return
ONLY valid JSON:
{
  "overall_score": 0-100,
  "verdict": "STRONG GO | CONDITIONAL GO | PIVOT NEEDED | NO GO",
  "dimensions": {
    "problem_clarity":     {"score": 0-10, "note": "..."},
    "market_timing":       {"score": 0-10, "note": "..."},
    "monetisation":        {"score": 0-10, "note": "..."},
    "defensibility":       {"score": 0-10, "note": "..."},
    "founder_market_fit":  {"score": 0-10, "note": "..."}
  },
  "top_risks": ["risk 1", "risk 2", "risk 3"],
  "recommended_pivots": ["pivot 1", "pivot 2"],
  "next_steps": ["step 1", "step 2", "step 3"]
}
Return ONLY JSON."""


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def score_viability(idea: str, client: httpx.AsyncClient) -> dict:
    """Score the viability of the given startup idea."""
    raw = await nvidia_chat(SYSTEM, idea, client)
    await asyncio.sleep(2)

    # First parse attempt
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        logger.warning("Viability JSON parse failed — retrying with strict prompt")

    # Retry with stricter prompt
    try:
        raw2 = await nvidia_chat(SYSTEM, idea + "\nReturn ONLY raw JSON", client)
        await asyncio.sleep(2)
        return json.loads(_strip_fences(raw2))
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Viability module failed after retry: %s", exc)
        return {"error": True}
