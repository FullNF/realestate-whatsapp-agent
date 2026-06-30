"""
Admin routes — everything here requires the X-Admin-Key header matching
ADMIN_API_KEY. These back the static/admin.html mini-dashboard, but work
fine from curl/Postman too.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_admin_key
from app.db.models import Lead, LeadControl
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_admin_key)])


@router.get("/leads")
async def list_leads(db: Session = Depends(get_db)) -> list[dict]:
    leads = db.execute(select(Lead).order_by(Lead.last_message_at.desc())).scalars().all()
    return [
        {
            "phone": l.phone,
            "name": l.name,
            "area_requested": l.area_requested,
            "bhk_requested": l.bhk_requested,
            "furnishing_pref": l.furnishing_pref,
            "budget_mentioned": l.budget_mentioned,
            "status": l.status,
            "out_of_area_attempts": l.out_of_area_attempts,
            "last_message_at": l.last_message_at.isoformat() if l.last_message_at else None,
        }
        for l in leads
    ]


@router.get("/exceptions")
async def list_exceptions(db: Session = Depends(get_db)) -> list[dict]:
    controls = db.execute(select(LeadControl)).scalars().all()
    return [
        {"phone": c.phone, "agent_enabled": c.agent_enabled, "reason": c.reason}
        for c in controls
    ]


@router.post("/leads/{phone}/reset")
async def reset_lead(phone: str, db: Session = Depends(get_db)) -> dict:
    """Wipes a lead's conversation history and captured fields so you can
    test from a clean slate without the AI seeing old messages. Does NOT
    touch the exception-list pause state."""
    lead = db.execute(select(Lead).where(Lead.phone == phone)).scalar_one_or_none()
    if lead is None:
        return {"status": "no_existing_lead", "phone": phone}
    db.delete(lead)
    db.commit()
    return {"status": "reset", "phone": phone}


@router.post("/leads/{phone}/pause")
async def pause_lead(phone: str, reason: str = "", db: Session = Depends(get_db)) -> dict:
    control = db.execute(select(LeadControl).where(LeadControl.phone == phone)).scalar_one_or_none()
    if control is None:
        control = LeadControl(phone=phone, agent_enabled=False, reason=reason)
        db.add(control)
    else:
        control.agent_enabled = False
        control.reason = reason
    db.commit()
    return {"status": "paused", "phone": phone}


@router.post("/leads/{phone}/resume")
async def resume_lead(phone: str, db: Session = Depends(get_db)) -> dict:
    control = db.execute(select(LeadControl).where(LeadControl.phone == phone)).scalar_one_or_none()
    if control is None:
        control = LeadControl(phone=phone, agent_enabled=True)
        db.add(control)
    else:
        control.agent_enabled = True
    db.commit()
    return {"status": "resumed", "phone": phone}


@router.get("/inventory")
async def list_inventory() -> list[dict]:
    """Reads straight from the same Google Sheet the CRM's Property
    Gallery writes to — there is nothing to upload here anymore, this
    just lets you verify what the agent is currently seeing."""
    from app.services import sheets_inventory

    return sheets_inventory.get_all_properties()
