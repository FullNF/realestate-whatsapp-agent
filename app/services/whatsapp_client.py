"""
Thin client around Meta's WhatsApp Cloud API (official, non-risky route —
see README for why this replaces unofficial libraries like Baileys).

Docs reference: https://developers.facebook.com/docs/whatsapp/cloud-api
"""

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = f"https://graph.facebook.com/{settings.META_API_VERSION}/{settings.META_PHONE_NUMBER_ID}/messages"


async def send_text_message(to_phone: str, body: str) -> bool:
    """Sends a free-form text reply. Only valid inside an open 24h
    customer-service window (i.e. the customer messaged you first/recently)
    — which is exactly our use case."""
    headers = {
        "Authorization": f"Bearer {settings.META_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "text",
        "text": {"body": body},
    }
    timeout = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=5.0)
    transport = httpx.AsyncHTTPTransport(retries=2)
    try:
        async with httpx.AsyncClient(timeout=timeout, transport=transport) as client:
            resp = await client.post(_BASE_URL, headers=headers, json=payload)
        if resp.status_code >= 400:
            logger.error("WhatsApp send failed (%s): %s", resp.status_code, resp.text)
            return False
        return True
    except httpx.HTTPError as exc:
        logger.error("WhatsApp send raised an exception: %s", exc)
        return False


async def notify_admin(text: str) -> None:
    """Pings your own WhatsApp number (ADMIN_NOTIFY_PHONE) for events you
    don't want to miss: a paused lead messaging in, or a hot/site-visit
    lead. No-op if ADMIN_NOTIFY_PHONE isn't configured."""
    if not settings.ADMIN_NOTIFY_PHONE:
        return
    await send_text_message(settings.ADMIN_NOTIFY_PHONE, f"[Agent] {text}")
