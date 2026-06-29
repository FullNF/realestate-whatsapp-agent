"""
Admin routes — everything here requires the X-Admin-Key header matching
ADMIN_API_KEY. These back the static/admin.html mini-dashboard, but work
fine from curl/Postman too.
"""

import csv
import io
import logging

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_admin_key
from app.db.models import AreaInventory, Lead, LeadControl
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
async def list_inventory(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(select(AreaInventory)).scalars().all()
    return [
        {
            "id": r.id,
            "sector": r.sector,
            "project_name": r.project_name,
            "bhk_type": r.bhk_type,
            "available_label": r.available_label,
            "price_raw": r.price_raw,
            "price_semi_furnished": r.price_semi_furnished,
            "price_fully_furnished": r.price_fully_furnished,
            "is_active": r.is_active,
        }
        for r in rows
    ]


@router.post("/inventory/import")
async def import_inventory(file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    """
    Upload a CSV with columns: sector,project_name,bhk_type,available_label,
    price_raw,price_semi_furnished,price_fully_furnished,notes
    (see area_inventory_template.csv in the repo). Replaces all existing
    rows — simplest correct behaviour for a small, fully-owned table.
    """
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    db.query(AreaInventory).delete()

    count = 0
    for row in reader:
        db.add(
            AreaInventory(
                sector=row.get("sector", "").strip(),
                project_name=(row.get("project_name") or "").strip() or None,
                bhk_type=row.get("bhk_type", "").strip(),
                available_label=(row.get("available_label") or "").strip() or None,
                price_raw=(row.get("price_raw") or "").strip() or None,
                price_semi_furnished=(row.get("price_semi_furnished") or "").strip() or None,
                price_fully_furnished=(row.get("price_fully_furnished") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
                is_active=True,
            )
        )
        count += 1

    db.commit()
    return {"status": "imported", "rows": count}
