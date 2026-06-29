"""
This is where every incoming WhatsApp message actually gets handled.

Flow per message:
  1. Idempotency check (Meta can redeliver the same webhook).
  2. Load/create the Lead, check the exception list (paused leads never
     reach the LLM at all).
  3. Extraction call: pull structured fields out of the conversation.
  4. Deterministic routing in code: in-area vs out-of-area vs not-enough-
     info-yet, including the out-of-area attempt counter and the final
     close-out decision. The LLM never makes this call itself.
  5. Response call: generate the actual reply text for the chosen mode.
  6. Send it, persist everything, optionally notify the admin.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Lead, LeadControl, Message
from app.prompts.system_prompt import EXTRACTION_SYSTEM_PROMPT, build_response_system_prompt
from app.services import inventory_service, whatsapp_client
from app.services.llm_client import chat_json

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 16


def _get_or_create_lead(db: Session, phone: str, contact_name: str | None) -> Lead:
    lead = db.execute(select(Lead).where(Lead.phone == phone)).scalar_one_or_none()
    if lead is None:
        lead = Lead(phone=phone, name=contact_name)
        db.add(lead)
        db.flush()
    return lead


def _is_paused(db: Session, phone: str) -> tuple[bool, str | None]:
    control = db.execute(select(LeadControl).where(LeadControl.phone == phone)).scalar_one_or_none()
    if control and not control.agent_enabled:
        return True, control.reason
    return False, None


def _build_transcript(db: Session, lead: Lead) -> str:
    msgs = (
        db.execute(
            select(Message)
            .where(Message.lead_id == lead.id)
            .order_by(Message.created_at.desc())
            .limit(HISTORY_LIMIT)
        )
        .scalars()
        .all()
    )
    msgs = list(reversed(msgs))
    lines = []
    for m in msgs:
        speaker = "Customer" if m.direction == "in" else settings.AGENT_NAME
        lines.append(f"{speaker}: {m.body}")
    return "\n".join(lines)


async def process_incoming_message(
    db: Session,
    *,
    phone: str,
    wa_message_id: str,
    text: str,
    contact_name: str | None = None,
) -> None:
    # 1. Idempotency
    existing = db.execute(
        select(Message).where(Message.wa_message_id == wa_message_id)
    ).scalar_one_or_none()
    if existing is not None:
        logger.info("Duplicate webhook delivery for message %s, skipping.", wa_message_id)
        return

    # 2. Lead + exception list
    lead = _get_or_create_lead(db, phone, contact_name)

    paused, reason = _is_paused(db, phone)
    if paused:
        db.add(Message(lead_id=lead.id, direction="in", wa_message_id=wa_message_id, body=text))
        db.commit()
        logger.info("Lead %s is paused (%s) — storing message only, no AI reply.", phone, reason)
        await whatsapp_client.notify_admin(
            f"Message from paused lead {phone} ({lead.name or 'no name'}): {text}"
        )
        return

    # Reactivate a previously closed-out lead if they come back
    if lead.status == "closed_out_of_area":
        lead.status = "active"
        lead.out_of_area_attempts = 0

    db.add(Message(lead_id=lead.id, direction="in", wa_message_id=wa_message_id, body=text))
    db.flush()

    transcript = _build_transcript(db, lead)

    # 3. Extraction call
    try:
        extracted = await chat_json(
            EXTRACTION_SYSTEM_PROMPT,
            f"Conversation so far:\n{transcript}\n\nExtract the fields now.",
        )
    except Exception:
        logger.exception("Extraction call failed, falling back to existing lead data.")
        extracted = {}

    for field in ("name", "area_requested", "bhk_requested", "furnishing_pref",
                  "budget_mentioned", "timeline_mentioned"):
        value = extracted.get(field)
        if value:
            setattr(lead, field, value)
    wants_site_visit = bool(extracted.get("wants_site_visit"))

    # 4. Deterministic routing
    mode = "collect_basic_info"
    context_data = ""
    attempt_info = ""

    if not lead.area_requested or not lead.bhk_requested:
        mode = "collect_basic_info"
    else:
        matched_area = inventory_service.find_matching_service_area(lead.area_requested)
        if matched_area:
            rows = inventory_service.get_teaser_rows(db, matched_area, lead.bhk_requested)
            context_data = inventory_service.format_teaser(rows)
            mode = "in_area_teaser"
            if wants_site_visit:
                lead.status = "site_visit_requested"
                await whatsapp_client.notify_admin(
                    f"Hot lead! {lead.name or phone} wants a site visit "
                    f"({lead.area_requested}, {lead.bhk_requested})."
                )
        else:
            lead.out_of_area_attempts += 1
            if lead.out_of_area_attempts >= settings.OUT_OF_AREA_MAX_ATTEMPTS:
                mode = "out_of_area_closeout"
                lead.status = "closed_out_of_area"
            else:
                mode = "out_of_area_redirect"
                attempt_info = f"{lead.out_of_area_attempts} of {settings.OUT_OF_AREA_MAX_ATTEMPTS}"
                context_data = inventory_service.get_alternatives_teaser(db, lead.area_requested)

    # 5. Response call
    response_system_prompt = build_response_system_prompt(
        mode, context_data=context_data, attempt_info=attempt_info
    )
    try:
        response = await chat_json(
            response_system_prompt,
            f"Conversation so far:\n{transcript}\n\nWrite your next reply now, "
            f'as JSON: {{"reply_text": "..."}}',
        )
        reply_text = response.get("reply_text", "").strip()
    except Exception:
        logger.exception("Response call failed.")
        reply_text = "Sorry, kuch technical issue aa gaya. Thodi der mein dobara try karta hoon."

    if not reply_text:
        reply_text = "Sorry, ek baar phir bata sakte hain aap kya dhund rahe hain?"

    # 6. Send + persist
    sent = await whatsapp_client.send_text_message(phone, reply_text)
    if sent:
        db.add(Message(lead_id=lead.id, direction="out", wa_message_id=None, body=reply_text))
    lead.last_message_at = datetime.now(timezone.utc)
    db.commit()
