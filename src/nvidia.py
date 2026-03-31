"""NVIDIA NIM API client with retry logic for free-tier rate limits."""

import asyncio
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.3-70b-instruct"


async def nvidia_chat(system: str, user: str, client: httpx.AsyncClient) -> str:
    """Send a chat completion request to the NVIDIA NIM API.

    Retry logic:
      - On HTTP 429 (rate limited): sleep 30 s and retry once.
      - On second 429: raise the exception.
      - On 5xx: log and raise immediately.
    """
    headers = {
        "Authorization": f"Bearer {settings.nvidia_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": NVIDIA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    for attempt in range(2):
        try:
            r = await client.post(
                f"{NVIDIA_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 and attempt == 0:
                logger.warning("NVIDIA 429 rate-limited — sleeping 30 s then retrying…")
                await asyncio.sleep(30)
                continue
            logger.error("NVIDIA API error %s: %s", exc.response.status_code, exc.response.text[:200])
            raise
