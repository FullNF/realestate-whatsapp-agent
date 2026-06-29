"""
The two endpoints Meta talks to:

GET  /webhook  — the one-time verification handshake when you configure
                 the webhook URL in the Meta app dashboard.
POST /webhook  — every actual message/status event. We verify the
                 signature, parse out real text messages, and hand them
                 to lead_service. We always return 200 quickly so Meta
                 doesn't retry-storm us; slow LLM work happens before the
                 response only because Render's free tier has no
                 background task runner — if you add one later, ack
                 immediately and process in the background instead.
"""

import logging

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import verify_meta_signature
from app.db.session import get_db
from app.services.lead_service import process_incoming_message

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/webhook")
async def verify_webhook(request: Request) -> Response:
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="Verification failed", status_code=403)


@router.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    raw_body = await request.body()
    signature = request.headers.get("x-hub-signature-256")

    if not verify_meta_signature(raw_body, signature):
        logger.warning("Webhook signature verification failed — ignoring payload.")
        # Still return 200 so Meta doesn't keep retrying a request it
        # thinks failed; we just don't act on it.
        return {"status": "ignored"}

    payload = await request.json()

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])
            contacts = value.get("contacts", [])
            contact_name = None
            if contacts:
                contact_name = contacts[0].get("profile", {}).get("name")

            for msg in messages:
                msg_type = msg.get("type")
                from_phone = msg.get("from")
                wa_message_id = msg.get("id")

                if msg_type == "text":
                    text = msg.get("text", {}).get("body", "")
                else:
                    # Media handling comes in a later module — for now,
                    # acknowledge politely so the customer isn't ignored.
                    text = f"[Customer sent a {msg_type} message]"

                await process_incoming_message(
                    db,
                    phone=from_phone,
                    wa_message_id=wa_message_id,
                    text=text,
                    contact_name=contact_name,
                )

    return {"status": "received"}
