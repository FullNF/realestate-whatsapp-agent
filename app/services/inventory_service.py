"""
Every price/availability sentence the agent says comes from this module,
not from the LLM's own "memory" — and now it reads straight from the
same Google Sheet the CRM's Property Gallery writes to. This is the
single most important safety property of the whole system: the LLM
phrases things naturally, but it never gets to make up a number.
"""

from collections import defaultdict

from app.config import settings
from app.services import sheets_inventory


def _matches_area(row_location: str, area_text: str) -> bool:
    a = (row_location or "").lower().strip()
    b = (area_text or "").lower().strip()
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    a_digits = "".join(ch for ch in a if ch.isdigit())
    b_digits = "".join(ch for ch in b if ch.isdigit())
    return bool(a_digits) and a_digits == b_digits


def find_matching_service_area(area_text: str) -> str | None:
    """Returns the service area name (taken live from the sheet's
    distinct locations) this text matches, or None if it doesn't match
    any sector currently present in the Properties sheet."""
    if not area_text:
        return None
    for area in sheets_inventory.get_service_areas():
        if _matches_area(area, area_text):
            return area
    return None


def get_teaser_rows(area_text: str, bhk_text: str | None = None) -> list[dict]:
    rows = sheets_inventory.get_all_properties()
    matched = [r for r in rows if _matches_area(r.get("location", ""), area_text)]
    if bhk_text:
        bhk_norm = bhk_text.lower().replace(" ", "")
        narrowed = [
            r for r in matched
            if bhk_norm in str(r.get("propertyType", "")).lower().replace(" ", "")
        ]
        if narrowed:
            matched = narrowed
    return matched[:8]  # never dump the whole sheet into a WhatsApp message


def format_teaser(rows: list[dict]) -> str:
    if not rows:
        return "No matching inventory rows found for this area/BHK combination."

    # Group by (location, propertyType) so all furnishing tiers for the
    # same kind of unit show up together, since the sheet stores one row
    # per furnishing tier rather than three price columns.
    grouped: dict = defaultdict(list)
    for r in rows:
        key = (r.get("location", ""), r.get("propertyType", ""))
        grouped[key].append(r)

    lines = []
    for (location, ptype), items in grouped.items():
        tiers = []
        for item in items:
            furnishing = item.get("furnishing") or "price on request"
            price = item.get("priceRange") or "price on request"
            project = item.get("name")
            project_str = f" ({project})" if project else ""
            tiers.append(f"{furnishing}: {price}{project_str}")
        lines.append(f"- {location}, {ptype}: " + "; ".join(tiers))
    return "\n".join(lines)


def get_alternatives_teaser(exclude_area: str | None) -> str:
    """Used for the out-of-area redirect: a short sample from areas you
    DO serve, to offer as an alternative."""
    rows = sheets_inventory.get_all_properties()
    if exclude_area:
        rows = [r for r in rows if not _matches_area(r.get("location", ""), exclude_area)]
    return format_teaser(rows[:6])
