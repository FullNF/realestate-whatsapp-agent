"""
Groq is used because it's the only genuinely free, no-card, fast LLM API
that's viable on free hosting (Render/Vercel free tiers can't run a local
model — no GPU, no persistent RAM for it). Groq's REST API is
OpenAI-compatible, so no special SDK is needed — plain httpx is enough,
keeping requirements.txt small.

Free tier limits (~30 requests/min, ~14,400/day at time of writing) are
plenty for a single WhatsApp business line. If you outgrow it, Groq's
paid Developer tier just needs a card on file, no code change.
"""

import json
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


async def chat_json(system_prompt: str, user_prompt: str) -> dict:
    """
    Calls Groq with response_format=json_object so the model is forced to
    return valid JSON we can parse directly — used for both the
    extraction call and the reply-generation call.

    Render's free-tier outbound networking occasionally has transient
    connection failures (ConnectTimeout) that resolve on retry — this is
    a known gotcha, not a Groq problem. `AsyncHTTPTransport(retries=2)`
    retries failed connection attempts automatically before giving up.
    """
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
    }

    timeout = httpx.Timeout(connect=10.0, read=20.0, write=10.0, pool=5.0)
    transport = httpx.AsyncHTTPTransport(retries=2)

    async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
        resp = await client.post(_GROQ_URL, headers=headers, json=payload)

    if resp.status_code >= 400:
        logger.error("Groq call failed (%s): %s", resp.status_code, resp.text)
        raise RuntimeError(f"Groq API error: {resp.status_code}")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.error("Groq returned non-JSON content: %s", content)
        raise
