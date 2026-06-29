"""
Every price/availability sentence the agent says comes from this module,
not from the LLM's own "memory". This is the single most important
safety property of the whole system: the LLM phrases things naturally,
but it never gets to make up a number.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AreaInventory


def _matches_area(row_sector: str, area_text: str) -> bool:
    a = row_sector.lower().strip()
    b = area_text.lower().strip()
    if a in b or b in a:
        return True
    # Compare digits too, so "70" matches "Sector 70"
    a_digits = "".join(ch for ch in a if ch.isdigit())
    b_digits = "".join(ch for ch in b if ch.isdigit())
    return bool(a_digits) and a_digits == b_digits


def find_matching_service_area(area_text: str) -> str | None:
    """Returns the configured service-area name this text matches, or
    None if it doesn't match any of your configured SERVICE_AREAS."""
    if not area_text:
        return None
    for area in settings.service_areas_list:
        if _matches_area(area, area_text):
            return area
    return None


def get_teaser_rows(db: Session, area_text: str, bhk_text: str | None = None) -> list[AreaInventory]:
    stmt = select(AreaInventory).where(AreaInventory.is_active.is_(True))
    rows = db.execute(stmt).scalars().all()
    matched = [r for r in rows if _matches_area(r.sector, area_text)]
    if bhk_text:
        bhk_norm = bhk_text.lower().replace(" ", "")
        narrowed = [r for r in matched if bhk_norm in r.bhk_type.lower().replace(" ", "")]
        if narrowed:
            matched = narrowed
    return matched[:5]  # never dump the whole table into a WhatsApp message


def format_teaser(rows: list[AreaInventory]) -> str:
    if not rows:
        return "No matching inventory rows found for this area/BHK combination."
    lines = []
    for r in rows:
        project = f" ({r.project_name})" if r.project_name else ""
        avail = r.available_label or "a few options"
        prices = []
        if r.price_raw:
            prices.append(f"raw: {r.price_raw}")
        if r.price_semi_furnished:
            prices.append(f"semi-furnished: {r.price_semi_furnished}")
        if r.price_fully_furnished:
            prices.append(f"fully-furnished: {r.price_fully_furnished}")
        price_str = ", ".join(prices) if prices else "price on request"
        lines.append(f"- {r.sector}{project}, {r.bhk_type}: {avail} available, {price_str}")
    return "\n".join(lines)


def get_alternatives_teaser(db: Session, exclude_area: str | None) -> str:
    """Used for the out-of-area redirect: a short sample from areas you
    DO serve, to offer as an alternative."""
    stmt = select(AreaInventory).where(AreaInventory.is_active.is_(True))
    rows = db.execute(stmt).scalars().all()
    if exclude_area:
        rows = [r for r in rows if not _matches_area(r.sector, exclude_area)]
    return format_teaser(rows[:4])
