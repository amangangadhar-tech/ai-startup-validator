"""Module 2 — Competitor Finder.

Calls NVIDIA NIM to identify direct/indirect competitors, market gaps,
and differentiation opportunities.  Returns a parsed dict.
"""

import asyncio
import json
import logging
import re

import httpx

from src.nvidia import nvidia_chat

logger = logging.getLogger(__name__)

SYSTEM = """You are a competitive intelligence researcher. Given a startup idea return ONLY
valid JSON:
{
  "direct_competitors": [
    {"name": "...", "stage": "seed|series_a|public", "est_arr": "...", "weakness": "..."}
  ],
  "indirect_competitors": ["name1", "name2"],
  "market_gaps": ["gap 1", "gap 2"],
  "differentiation_opportunities": ["opp 1", "opp 2"],
  "competitive_intensity": "low|medium|high|extreme"
}
Return ONLY JSON."""


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def find_competitors(idea: str, client: httpx.AsyncClient) -> dict:
    """Discover competitors for the given startup idea."""
    raw = await nvidia_chat(SYSTEM, idea, client)
    await asyncio.sleep(2)

    # First parse attempt
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        logger.warning("Competitors JSON parse failed — retrying with strict prompt")

    # Retry with stricter prompt
    try:
        raw2 = await nvidia_chat(SYSTEM, idea + "\nReturn ONLY raw JSON", client)
        await asyncio.sleep(2)
        return json.loads(_strip_fences(raw2))
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Competitors module failed after retry: %s", exc)
        return {"error": True}
