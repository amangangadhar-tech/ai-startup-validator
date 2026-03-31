"""Module 1 — Market Trend Analyser.

Calls NVIDIA NIM to analyse market size, growth, trends, and risks
for a given startup idea.  Returns a parsed dict.
"""

import asyncio
import json
import logging
import re

import httpx

from src.nvidia import nvidia_chat

logger = logging.getLogger(__name__)

SYSTEM = """You are a market research analyst. Analyse the startup idea given and return ONLY
valid JSON with these exact keys:
{
  "market_size": "string (e.g. '$4.2B TAM')",
  "growth_rate": "string (e.g. '18% CAGR 2024-2028')",
  "trend_signals": ["list", "of", "3-5", "bullet strings"],
  "hot_verticals": ["list of adjacent hot spaces"],
  "risk_signals":  ["list of headwinds"],
  "confidence": 0-100
}
Return ONLY JSON. No markdown. No preamble."""


def _strip_fences(text: str) -> str:
    """Remove ```json ... ``` fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def analyse_market(idea: str, client: httpx.AsyncClient) -> dict:
    """Analyse market trends for the given startup idea."""
    raw = await nvidia_chat(SYSTEM, idea, client)
    await asyncio.sleep(2)  # rate-limit breathing room

    # First parse attempt
    try:
        return json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        logger.warning("Market JSON parse failed — retrying with strict prompt")

    # Retry with stricter prompt
    try:
        raw2 = await nvidia_chat(SYSTEM, idea + "\nReturn ONLY raw JSON", client)
        await asyncio.sleep(2)
        return json.loads(_strip_fences(raw2))
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Market module failed after retry: %s", exc)
        return {"error": True}
